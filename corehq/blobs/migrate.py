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
from base64 import b64encode
from datetime import datetime
from tempfile import mkdtemp

from django.conf import settings
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.mixin import BlobHelper
from corehq.blobs.models import BlobMigrationState
from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type
from corehq.util.couch_helpers import (
    ResumableDocsByTypeIterator,
    TooManyRetries,
)
from couchdbkit import ResourceConflict

# models to be migrated
import corehq.apps.hqmedia.models as hqmedia
import couchforms.models as xform
from corehq.apps.app_manager.models import Application, RemoteApp
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


class BaseDocMigrator(object):

    #blobs_key = None  # Abstract: doc key to be tested for migration status.
    # If this key contains a falsy value the document will not be migrated.

    # If true, load attachment content before migrating.
    load_attachments = False

    def migrate(self, doc, couchdb):
        """Migrate a single document

        :param doc: The document dict to be migrated.
        :param couchdb: Couchdb database in which to save migrated doc.
        :returns: True if doc was migrated else False. If this returns False
        the document migration will be retried later.
        """
        raise NotImplementedError("abstract method")

    def after_migration(self):
        pass


class CouchAttachmentMigrator(BaseDocMigrator):

    blobs_key = "_attachments"
    load_attachments = True

    def migrate(self, doc, couchdb):
        attachments = doc.pop("_attachments")
        external_blobs = doc.setdefault("external_blobs", {})
        obj = BlobHelper(doc, couchdb)
        try:
            with obj.atomic_blobs():
                for name, data in list(attachments.iteritems()):
                    if name in external_blobs:
                        continue  # skip attachment already in blob db
                    obj.put_attachment(name=name, **data)
        except ResourceConflict:
            # Do not migrate document if `atomic_blobs()` fails.
            # This is an unlikely state, but could happen if the
            # document is (externally) modified between when the
            # migration fetches and processes the document.
            return False
        return True


class BlobDbBackendMigrator(BaseDocMigrator):

    blobs_key = "external_blobs"

    def __init__(self):
        self.db = get_blob_db()
        self.total_blobs = 0
        self.not_found = 0
        if not isinstance(self.db, MigratingBlobDB):
            raise MigrationError(
                "Expected to find migrating blob db backend (got %r)" % self.db)

    def migrate(self, doc, couchdb):
        obj = BlobHelper(doc, couchdb)
        bucket = obj._blobdb_bucket()
        assert obj.external_blobs and obj.external_blobs == obj.blobs, doc
        for name, meta in obj.blobs.iteritems():
            self.total_blobs += 1
            try:
                content = self.db.old_db.get(meta.id, bucket)
            except NotFound:
                self.not_found += 1
            else:
                with content:
                    self.db.copy_blob(content, meta.info, bucket)
        return True

    def after_migration(self):
        if self.not_found:
            print("{} of {} blobs were not found in the old blob database. It "
                  "is possible that some blobs were deleted as part of normal "
                  "operation during the migration if the migration took a long "
                  "time. However, it may be cause for concern if a majority of "
                  "the total number of migrated blobs were not found."
                  .format(self.not_found, self.total_blobs))


class Migrator(object):

    def __init__(self, slug, doc_types, doc_migrator_class):
        self.slug = slug
        self.doc_migrator_class = doc_migrator_class
        self.doc_type_map = dict(
            t if isinstance(t, tuple) else (t.__name__, t) for t in doc_types)
        if len(doc_types) != len(self.doc_type_map):
            raise ValueError("Invalid (duplicate?) doc types")

    def migrate(self, *args, **kw):
        return migrate(
            self.slug,
            self.doc_type_map,
            self.doc_migrator_class,
            *args, **kw
        )


MIGRATIONS = {m.slug: m for m in [
    Migrator("saved_exports", [SavedBasicExport], CouchAttachmentMigrator),
    Migrator("migrate_backend", [SavedBasicExport], BlobDbBackendMigrator),
    Migrator("applications", [
        Application,
        RemoteApp,
        ("Application-Deleted", Application),
        ("RemoteApp-Deleted", RemoteApp),
    ], CouchAttachmentMigrator),
    Migrator("multimedia", [
        hqmedia.CommCareAudio,
        hqmedia.CommCareImage,
        hqmedia.CommCareVideo,
        hqmedia.CommCareMultimedia,
    ], CouchAttachmentMigrator),
    Migrator("xforms", [
        xform.XFormInstance,
        ("XFormInstance-Deleted", xform.XFormInstance),
        xform.XFormArchived,
        xform.XFormDeprecated,
        xform.XFormDuplicate,
        xform.XFormError,
        xform.SubmissionErrorLog,
    ], CouchAttachmentMigrator),
]}


def migrate(slug, doc_type_map, doc_migrator_class, filename=None, reset=False,
            max_retry=2):
    """Migrate blobs

    :param slug: Migration name.
    :param doc_type_map: Dict of `doc_type_name: model_class` pairs.
    :param doc_migrator_class: A `BaseDocMigrator` subclass used to
    migrate documents.
    :param filename: File path for intermediate storage of migration
    data.
    :param reset: Reset existing migration state (if any), causing all
    documents to be reconsidered for migration, if this is true. This
    does not reset the django migration flag.
    flag, which is set when the migration completes successfully.
    :param max_retry: Number of times to retry migrating a document
    before giving up.
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

    total = sum(get_doc_count_by_type(couchdb, doc_type)
                for doc_type in doc_type_map)
    print("Migrating {} documents: {}...".format(
        total,
        ", ".join(sorted(doc_type_map))
    ))
    migrated = 0
    skipped = 0
    visited = 0
    start = datetime.now()
    doc_migrator = doc_migrator_class()
    load_attachments = doc_migrator.load_attachments
    blobs_key = doc_migrator.blobs_key
    iter_key = slug + "-blob-migration"
    docs_by_type = ResumableDocsByTypeIterator(couchdb, doc_type_map, iter_key)
    if reset:
        docs_by_type.discard_state()

    with open(filename, 'wb') as f:
        for doc in docs_by_type:
            visited += 1
            if doc.get(blobs_key):
                if load_attachments:
                    obj = BlobHelper(doc, couchdb)
                    doc["_attachments"] = {
                        name: {
                            "content_type": meta["content_type"],
                            "content": obj.fetch_attachment(name),
                        }
                        for name, meta in doc["_attachments"].items()
                    }
                    # make copy with encoded attachments for JSON dump
                    backup_doc = dict(doc)
                    backup_doc["_attachments"] = {
                        name: {
                            "content_type": meta["content_type"],
                            "content": encode_content(meta["content"]),
                        }
                        for name, meta in doc["_attachments"].items()
                    }
                else:
                    backup_doc = doc
                f.write('{}\n'.format(json.dumps(backup_doc)))
                f.flush()
                ok = doc_migrator.migrate(doc, couchdb)
                if ok:
                    migrated += 1
                else:
                    try:
                        docs_by_type.retry(doc, max_retry)
                    except TooManyRetries:
                        print("Skip: {doc_type} {_id}".format(**doc))
                        skipped += 1
                if (migrated + skipped) % 100 == 0:
                    elapsed = datetime.now() - start
                    remaining = elapsed / visited * total
                    print("Migrated {}/{} of {} documents in {} ({} remaining)"
                          .format(migrated, visited, total, elapsed, remaining))

    doc_migrator.after_migration()

    if dirpath is not None:
        os.remove(filename)
        os.rmdir(dirpath)

    print("Migrated {}/{} of {} documents ({} previously migrated, {} had no attachments)."
        .format(
            migrated,
            visited,
            total,
            total - visited,
            visited - (migrated + skipped)
        ))
    if skipped:
        print(MIGRATIONS_SKIPPED_WARNING.format(skipped))
    else:
        BlobMigrationState.objects.get_or_create(slug=slug)[0].save()
    return migrated, skipped


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
