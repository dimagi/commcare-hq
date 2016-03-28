"""Migrate attachments from couchdb to an external blob store

## Running migrations

Use the `run_blob_migration` management command to transfer attachments
on selected models from couchdb to the external blob database. Run the
command without arguments to get a list of possible migrations that
can be run:

    ./manage.py run_blob_migration

The migration may be done automatically when running `./manage.py migrate`
if there are only a few documents to be migrated. However, if there are
many documents to be migrated then the normal migration process will
stop and propmpt you to run the blob migration manually before
continuing with the normal migration process.

## Writing new migrations

Complete each of the following steps when migrating a new set of couch
models' attachments to the blob database:

1. Add `BlobMixin` as a base class of each couch model with attachments
   to be migrated to the blob database. For each new `BlobMixin` model:

   a. The mixin must come before `Document` in the list of base classes.
   b. Add `migrating_blobs_from_couch = True` to the class.
   c. Adapt any uses of the `_attachments` property to use `blobs`
      instead (this is more than a simple find and replace; see
      `corehq.blobs.mixin` for details).

2. Add a `Migrator` instance to the list of `MIGRATIONS` in
   `corehq/blobs/migrate.py`. It will look something like
   `Migrator("<your_slug>", [<list of new BlobMixin couch models>])`.
   Don't forget to add a test to verify that your migration actually
   works.

3. Deploy.

4. Run the management command to migrate attachments out of couch:
   `./manage.py run_blob_migration <your_slug>`

5. Remove `migrating_blobs_from_couch = True` from each of your
   `BlobMixin` models.

6. Create a new django migration with the `makemigrations` management
   command:
   ```
   ./manage.py makemigrations --empty blobs
   ```
   Then modify the new migration, adding an operation:
   ```
   operations = [
       HqRunPython(*assert_migration_complete("<your_slug>"))
   ]
   ```
   Don't forget to put
   ```
   from corehq.blobs.migrate import assert_migration_complete
   from corehq.sql_db.operations import HqRunPython
   ```
   at the top of the file.

7. Deploy.

That's it, you're done!
"""
import json
import os
import traceback
from tempfile import mkdtemp

from django.conf import settings
from couchexport.models import SavedBasicExport
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.mixin import BlobMixin
from corehq.blobs.models import BlobMigrationState
from corehq.dbaccessors.couchapps.all_docs import (
    get_all_docs_with_doc_types,
    get_doc_count_by_type,
)
from couchdbkit import ResourceConflict, ResourceNotFound

MIGRATION_INSTRUCTIONS = """
There are {total} documents that may have attachments, and they must be
migrated to a new blob database.

Run these commands to procede with migrations:

./manage.py run_blob_migration {slug} --file=FILE
./manage.py migrate

Note: --file=FILE is optional and can be omitted if you do not want to
keep a copy of the couch documents that were migrated. Also note that
the copy of the couch documents will not include attachment content
because `get_all_docs_with_doc_types()` does not support that.

See also:
https://github.com/dimagi/commcare-hq/blob/master/corehq/blobs/migrate.py
"""

BLOB_DB_NOT_CONFIGURED = """
Cannot get the blob database.

This often means that settings.SHARED_DRIVE_ROOT is not configured.
It should be set to a real directory. Update localsettings.py and
retry the migration.
"""

MIGRATIONS_SKIPPED_WARNING = """
WARNING {} documents were not migrated due to concurrent modification
during migration. Run the migration again until you do not see this
message.
"""


def migrate_from_couch_to_blobdb(filename, type_map, total):
    """Migrate attachments from couchdb to blob storage
    """
    skips = 0
    with open(filename, 'r') as f:
        for n, line in enumerate(f):
            if n % 100 == 0:
                print_status(n + 1, total)
            doc = json.loads(line)
            obj = type_map[doc["doc_type"]](doc)
            fetch_attachment = super(BlobMixin, obj).fetch_attachment
            try:
                with obj.atomic_blobs():
                    for name, meta in list(obj._attachments.iteritems()):
                        try:
                            content = fetch_attachment(name, stream=True)
                        except ResourceNotFound:
                            # ignore attachment that has been removed
                            continue
                        obj.put_attachment(
                            content, name, content_type=meta["content_type"])
            except ResourceConflict:
                # Do not migrate document if `atomic_blobs()` fails.
                # This is an unlikely state, but could happen if the
                # document is (externally) modified between when the
                # migration fetches and processes the document.
                skips += 1
    return total, skips

migrate_from_couch_to_blobdb.blobs_key = "_attachments"


def migrate_blob_db_backend(filename, type_map, total):
    """Copy blobs from old blob db to new blob db

    This is an idempotent operation. It is safe to interrupt and/or run
    it more than once for a given pair of blob dbs. Running it more than
    once may be very innefficient (it may copy the full content of every
    blob each time), depending on the implementation of the databases
    being migrated.
    """
    db = get_blob_db()
    if not isinstance(db, MigratingBlobDB):
        raise MigrationError(
            "Expected to find migrating blob db backend (got %r)" % db)

    not_found = 0
    with open(filename, 'r') as f:
        for n, line in enumerate(f):
            if n % 100 == 0:
                print_status(n + 1, total)
            doc = json.loads(line)
            obj = type_map[doc["doc_type"]](doc)
            bucket = obj._blobdb_bucket()
            assert obj.external_blobs == obj.blobs, (obj.external_blobs, obj.blobs)
            for name, meta in obj.blobs.iteritems():
                try:
                    content = db.old_db.get(meta.id, bucket)
                except NotFound:
                    not_found += 1
                else:
                    with content:
                        db.copy_blob(content, meta.info, bucket)
    if not_found:
        print("{} documents were not found in the old blob database. It is "
              "possible that some blobs were deleted as part of normal "
              "operation during the migration if the migration took a long "
              "time. However, it may be cause for concern if a majority of "
              "the total number of migrated blobs were not found."
              .format(not_found))
    return total - not_found, 0

migrate_blob_db_backend.blobs_key = "external_blobs"


class Migrator(object):

    def __init__(self, slug, doc_types, migrate_func):
        self.slug = slug
        self.doc_types = doc_types
        self.migrate_func = migrate_func

    def migrate(self, filename=None):
        return migrate(self.slug, self.doc_types, self.migrate_func, filename)


MIGRATIONS = {m.slug: m for m in [
    Migrator("saved_exports", [SavedBasicExport], migrate_from_couch_to_blobdb),
    Migrator("migrate_backend", [SavedBasicExport], migrate_blob_db_backend),
]}


def migrate(slug, doc_types, migrate_func, filename=None):
    """Migrate blobs

    :param doc_types: List of couch model classes to be migrated.
    :param filename: File path for intermediate storage of migration data.
    :param migrate_func: A function `func(filename, type_map, total)`
    returning a tuple `(<num migrated>, <num skipped>)`. If `<num skipped>`
    is non-zero the migration will be considered failed (a migration state
    record will not be saved). `<num migrated>` need not match the original
    `total` passed in. This could happen, for example, if a document is
    deleted during the migration (and should not cause migration failure).
    :returns: A tuple `(<num migrated>, <num skipped>)`
    """
    couchdb = doc_types[0].get_db()
    assert all(t.get_db() is couchdb for t in doc_types[1:]), repr(doc_types)
    type_map = {cls.__name__: cls for cls in doc_types}

    dirpath = None
    if filename is None:
        dirpath = mkdtemp()
        filename = os.path.join(dirpath, "export.txt")

    print("Loading documents: {}...".format(", ".join(type_map)))
    total = 0
    with open(filename, 'w') as f:
        for doc in get_all_docs_with_doc_types(couchdb, list(type_map)):
            if doc.get(migrate_func.blobs_key):
                f.write('{}\n'.format(json.dumps(doc)))
                total += 1

    migrated, skips = migrate_func(filename, type_map, total)

    if dirpath is not None:
        os.remove(filename)
        os.rmdir(dirpath)

    print("Migrated {} documents.".format(migrated - skips))
    if skips:
        print(MIGRATIONS_SKIPPED_WARNING.format(skips))
    else:
        BlobMigrationState.objects.get_or_create(slug=slug)[0].save()
    return migrated - skips, skips


def print_status(num, total):
    print("Migrating {} of {} documents".format(num, total))


def assert_migration_complete(slug):

    def forwards(apps, schema_editor):
        if settings.UNIT_TESTING:
            return

        try:
            get_blob_db()
        except Exception:
            raise MigrationError(
                "Cannot get blob db:\n{error}{message}".format(
                    error=traceback.format_exc(),
                    message=BLOB_DB_NOT_CONFIGURED,
                ))

        try:
            BlobMigrationState.objects.get(slug=slug)
            return  # already migrated
        except BlobMigrationState.DoesNotExist:
            pass

        migrator = MIGRATIONS[slug]
        total = 0
        for doc_type in migrator.doc_types:
            total += get_doc_count_by_type(doc_type.get_db(), doc_type.__name__)
        if total > 500:
            message = MIGRATION_INSTRUCTIONS.format(slug=slug, total=total)
            raise MigrationNotComplete(message)

        # just do the migration if the number of documents is small
        migrated, skipped = migrator.migrate()
        if skipped:
            raise MigrationNotComplete(MIGRATIONS_SKIPPED_WARNING.format(skipped))

    def reverse(apps, schema_editor):
        # NOTE: this does not move blobs back into couch. It only
        # un-sets the blob migration state so it can be run again.
        # It is safe to run the forward migration more than once.
        try:
            model = BlobMigrationState.objects.get(slug=slug)
            model.delete()
        except BlobMigrationState.DoesNotExist:
            pass

    return forwards, reverse


class MigrationError(Exception):
    pass


class MigrationNotComplete(MigrationError):
    pass
