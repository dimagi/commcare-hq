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
from base64 import b64decode, b64encode
from datetime import datetime
from tempfile import mkdtemp

from django.conf import settings
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.mixin import BlobHelper
from corehq.blobs.models import BlobMigrationState
from corehq.dbaccessors.couchapps.all_docs import (
    get_all_docs_with_doc_types,
    get_doc_count_by_type,
)
from couchdbkit import ResourceConflict

# models to be migrated
from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.apps.hqmedia.models import (
    CommCareAudio,
    CommCareImage,
    CommCareMultimedia,
    CommCareVideo,
)
from couchexport.models import SavedBasicExport


MIGRATION_INSTRUCTIONS = """
There are {total} documents that may have attachments, and they must be
migrated to a new blob database.

Run these commands to proceed with migrations:

./manage.py run_blob_migration {slug} --file=FILE
./manage.py migrate

Note: --file=FILE is optional and can be omitted if you do not want to
keep a copy of the couch documents, including attachments, that were
migrated.

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


def migrate_from_couch_to_blobdb(filename, couchdb, total):
    """Migrate attachments from couchdb to blob storage
    """
    skips = 0
    start = datetime.now()
    with open(filename, 'r') as f:
        for n, line in enumerate(f):
            if n % 100 == 0:
                print_status(n + 1, total, datetime.now() - start)
            doc = json.loads(line)
            attachments = doc.pop("_attachments")
            external_blobs = doc.setdefault("external_blobs", {})
            obj = BlobHelper(doc, couchdb)
            try:
                with obj.atomic_blobs():
                    for name, data in list(attachments.iteritems()):
                        if name in external_blobs:
                            continue  # skip attachment already in blob db
                        data["content"] = b64decode(data["content"])
                        obj.put_attachment(name=name, **data)
            except ResourceConflict:
                # Do not migrate document if `atomic_blobs()` fails.
                # This is an unlikely state, but could happen if the
                # document is (externally) modified between when the
                # migration fetches and processes the document.
                skips += 1
    return total, skips

migrate_from_couch_to_blobdb.load_attachments = True
migrate_from_couch_to_blobdb.blobs_key = "_attachments"


def migrate_blob_db_backend(filename, couchdb, total):
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
    start = datetime.now()
    with open(filename, 'r') as f:
        for n, line in enumerate(f):
            if n % 100 == 0:
                print_status(n + 1, total, datetime.now() - start)
            doc = json.loads(line)
            obj = BlobHelper(doc, couchdb)
            bucket = obj._blobdb_bucket()
            assert obj.external_blobs and obj.external_blobs == obj.blobs, doc
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
        self.migrate_func = migrate_func
        self.doc_type_map = dict(
            t if isinstance(t, tuple) else (t.__name__, t) for t in doc_types)
        if len(doc_types) != len(self.doc_type_map):
            raise ValueError("Invalid (duplicate?) doc types")

    def migrate(self, filename=None):
        return migrate(self.slug, self.doc_type_map, self.migrate_func, filename)


MIGRATIONS = {m.slug: m for m in [
    Migrator("saved_exports", [SavedBasicExport], migrate_from_couch_to_blobdb),
    Migrator("migrate_backend", [SavedBasicExport], migrate_blob_db_backend),
    Migrator("applications", [
        Application,
        RemoteApp,
        ("Application-Deleted", Application),
        ("RemoteApp-Deleted", RemoteApp),
    ], migrate_from_couch_to_blobdb),
    Migrator("multimedia", [
        CommCareAudio,
        CommCareImage,
        CommCareVideo,
        CommCareMultimedia,
    ], migrate_from_couch_to_blobdb),
]}


def migrate(slug, doc_type_map, migrate_func, filename=None):
    """Migrate blobs

    :param doc_type_map: Dict of `doc_type_name: model_class` pairs.
    :param filename: File path for intermediate storage of migration data.
    :param migrate_func: A function `func(filename, type_map, total)`
    returning a tuple `(<num migrated>, <num skipped>)`. If `<num skipped>`
    is non-zero the migration will be considered failed (a migration state
    record will not be saved). `<num migrated>` need not match the original
    `total` passed in. This could happen, for example, if a document is
    deleted during the migration (and should not cause migration failure).
    :returns: A tuple `(<num migrated>, <num skipped>)`
    """
    couchdb = next(iter(doc_type_map.values())).get_db()
    assert all(m.get_db() is couchdb for m in doc_type_map.values()), \
        "documents must live in same couch db: %s" % repr(doc_type_map)

    dirpath = None
    if filename is None:
        dirpath = mkdtemp()
        filename = os.path.join(dirpath, "export.txt")

    def encode_content(data):
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        return b64encode(data)

    print("Loading documents: {}...".format(", ".join(doc_type_map)))
    total = 0
    start = datetime.now()
    load_attachments = getattr(migrate_func, "load_attachments", False)
    with open(filename, 'w') as f:
        for doc in get_all_docs_with_doc_types(couchdb, list(doc_type_map)):
            if doc.get(migrate_func.blobs_key):
                if load_attachments:
                    obj = BlobHelper(doc, couchdb)
                    fetch_attachment = obj.fetch_attachment
                    doc["_attachments"] = {
                        name: {
                            "content_type": meta["content_type"],
                            "content": encode_content(fetch_attachment(name)),
                        }
                        for name, meta in doc["_attachments"].items()
                    }
                f.write('{}\n'.format(json.dumps(doc)))
                total += 1
                if total % 100 == 0:
                    print("Loaded {} documents in {}"
                          .format(total, datetime.now() - start))

    migrated, skips = migrate_func(filename, couchdb, total)

    if dirpath is not None:
        os.remove(filename)
        os.rmdir(dirpath)

    print("Migrated {} documents.".format(migrated - skips))
    if skips:
        print(MIGRATIONS_SKIPPED_WARNING.format(skips))
    else:
        BlobMigrationState.objects.get_or_create(slug=slug)[0].save()
    return migrated - skips, skips


def print_status(num, total, elapsed):
    print("Migrating {} of {} documents in {}".format(num, total, elapsed))


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
        for doc_type, model_class in migrator.doc_type_map.items():
            total += get_doc_count_by_type(model_class.get_db(), doc_type)
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
