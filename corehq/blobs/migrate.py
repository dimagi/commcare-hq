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
stop and prompt you to run the blob migration manually before
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
from abc import abstractmethod
from base64 import b64encode
from tempfile import mkdtemp

from django.conf import settings

from corehq.apps.export import models as exports
from corehq.apps.ota.models import DemoUserRestore
from corehq.blobs import get_blob_db, DEFAULT_BUCKET, BlobInfo
from corehq.blobs.exceptions import NotFound
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.mixin import BlobHelper
from corehq.blobs.models import BlobMigrationState
from corehq.blobs.zipdb import get_export_filename
from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type
from corehq.util.doc_processor.couch import (
    CouchDocumentProvider, doc_type_tuples_to_dict, CouchViewDocumentProvider
)
from corehq.util.doc_processor.couch import CouchProcessorProgressLogger
from corehq.util.doc_processor.interface import (
    BaseDocProcessor, DOCS_SKIPPED_WARNING,
    DocumentProcessorController
)
from couchdbkit import ResourceConflict

# models to be migrated
import corehq.apps.hqmedia.models as hqmedia
import couchforms.models as xform
from corehq.apps.app_manager.models import Application, RemoteApp
from couchexport.models import SavedBasicExport
import corehq.form_processor.models as sql_xform

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

PROCESSING_COMPLETE_MESSAGE = """
{} of {} blobs were not found in the old blob database. It
is possible that some blobs were deleted as part of normal
operation during the migration if the migration took a long
time. However, it may be cause for concern if a majority of
the total number of migrated blobs were not found.
"""


def encode_content(data):
    if isinstance(data, unicode):
        data = data.encode("utf-8")
    return b64encode(data)


class BaseDocMigrator(BaseDocProcessor):

    # If true, load attachment content before migrating.
    load_attachments = False

    def __init__(self, slug, couchdb, filename=None):
        super(BaseDocMigrator, self).__init__()
        self.slug = slug
        self.couchdb = couchdb
        self.dirpath = None
        self.filename = filename
        if filename is None:
            self.dirpath = mkdtemp()
            self.filename = os.path.join(self.dirpath, "export.txt")

    def __enter__(self):
        print("Migration log: {}".format(self.filename))
        self.backup_file = open(self.filename, 'wb')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.backup_file.close()

    def handle_skip(self, doc):
        return True  # ignore

    def _prepare_doc(self, doc):
        if self.load_attachments:
            obj = BlobHelper(doc, self.couchdb)
            doc["_attachments"] = {
                name: {
                    "content_type": meta["content_type"],
                    "content": obj.fetch_attachment(name),
                }
                for name, meta in doc["_attachments"].items()
            }

    def _backup_doc(self, doc):
        if self.load_attachments:
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

        self.backup_file.write('{}\n'.format(json.dumps(backup_doc)))
        self.backup_file.flush()

    def process_doc(self, doc):
        """Migrate a single document

        :param doc: The document dict to be migrated.
        :returns: True if doc was migrated else False. If this returns False
        the document migration will be retried later.
        """
        self._prepare_doc(doc)
        self._backup_doc(doc)
        return self._do_migration(doc)

    @abstractmethod
    def _do_migration(self, doc):
        raise NotImplementedError

    def processing_complete(self, skipped):
        if self.dirpath is not None:
            os.remove(self.filename)
            os.rmdir(self.dirpath)

        if not skipped:
            BlobMigrationState.objects.get_or_create(slug=self.slug)[0].save()


class CouchAttachmentMigrator(BaseDocMigrator):

    load_attachments = True

    def _do_migration(self, doc):
        attachments = doc.pop("_attachments")
        external_blobs = doc.setdefault("external_blobs", {})
        obj = BlobHelper(doc, self.couchdb)
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

    def should_process(self, doc):
        return doc.get("_attachments")


class BlobDbBackendMigrator(BaseDocMigrator):

    def __init__(self, slug, couchdb, filename=None):
        super(BlobDbBackendMigrator, self).__init__(slug, couchdb, filename)
        self.db = get_blob_db()
        self.total_blobs = 0
        self.not_found = 0
        if not isinstance(self.db, MigratingBlobDB):
            raise MigrationError(
                "Expected to find migrating blob db backend (got %r)" % self.db)

    def _do_migration(self, doc):
        obj = BlobHelper(doc, self.couchdb)
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

    def processing_complete(self, skipped):
        super(BlobDbBackendMigrator, self).processing_complete(skipped)
        if self.not_found:
            print(PROCESSING_COMPLETE_MESSAGE.format(self.not_found, self.total_blobs))

    def should_process(self, doc):
        return doc.get("external_blobs")


class BlobDbBackendExporter(BaseDocProcessor):

    def __init__(self, slug, domain, couchdb):
        from corehq.blobs.zipdb import ZipBlobDB
        self.slug = slug
        self.db = ZipBlobDB(self.slug, domain)
        self.total_blobs = 0
        self.not_found = 0
        self.domain = domain
        self.couchdb = couchdb

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

    def process_doc(self, doc):
        obj = BlobHelper(doc, self.couchdb)
        bucket = obj._blobdb_bucket()
        assert obj.external_blobs and obj.external_blobs == obj.blobs, doc
        from_db = get_blob_db()
        for name, meta in obj.blobs.iteritems():
            self.total_blobs += 1
            try:
                content = from_db.get(meta.id, bucket)
            except NotFound:
                self.not_found += 1
            else:
                with content:
                    self.db.copy_blob(content, meta.info, bucket)
        return True

    def processing_complete(self, skipped):
        if self.not_found:
            print(PROCESSING_COMPLETE_MESSAGE.format(self.not_found, self.total_blobs))

    def should_process(self, doc):
        return doc.get("external_blobs")


class SqlObjectExporter(object):
    def __init__(self, slug, domain):
        from corehq.blobs.zipdb import ZipBlobDB
        self.slug = slug
        self.db = ZipBlobDB(self.slug, domain)
        self.total_blobs = 0
        self.not_found = 0
        self.domain = domain

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        self.processing_complete()

    def process_object(self, object):
        pass

    def processing_complete(self):
        if self.not_found:
            print("{} {} objects processed, {} blobs not found".format(
                self.total_blobs, self.slug, self.not_found
            ))
        else:
            print("{} {} objects processed".format(self.total_blobs, self.slug))


class SqlFormAttachmentExporter(SqlObjectExporter):
    def process_object(self, attachment):
        from_db = get_blob_db()
        bucket = attachment.blobdb_bucket()
        blob_id = attachment.blob_id
        info = BlobInfo(identifier=blob_id, length=attachment.content_length,
                        digest="md5=" + attachment.md5)
        self.total_blobs += 1
        try:
            content = from_db.get(blob_id, bucket)
        except NotFound:
            self.not_found += 1
        else:
            with content:
                self.db.copy_blob(content, info, bucket)


class DemoUserRestoreExporter(SqlObjectExporter):
    def process_object(self, object):
        blob_id = object.restore_blob_id
        info = BlobInfo(identifier=blob_id, length=object.content_length, digest=None)
        self.total_blobs += 1
        db = get_blob_db()
        try:
            content = db.get(blob_id)
        except NotFound:
            self.not_found += 1
        else:
            with content:
                self.db.copy_blob(content, info, DEFAULT_BUCKET)


class Migrator(object):

    def __init__(self, slug, doc_types, doc_migrator_class):
        self.slug = slug
        self.doc_migrator_class = doc_migrator_class
        self.doc_types = doc_types
        first_type = doc_types[0]
        self.couchdb = (first_type[0] if isinstance(first_type, tuple) else first_type).get_db()

        sorted_types = sorted(doc_type_tuples_to_dict(self.doc_types))
        self.iteration_key = "{}-blob-migration/{}".format(self.slug, " ".join(sorted_types))

    def migrate(self, filename=None, reset=False, max_retry=2, chunk_size=100):
        processor = DocumentProcessorController(
            self._get_document_provider(),
            self._get_doc_migrator(filename),
            reset,
            max_retry,
            chunk_size,
            progress_logger=self._get_progress_logger()
        )
        return processor.run()

    def _get_doc_migrator(self, filename):
        return self.doc_migrator_class(self.slug, self.couchdb, filename)

    def _get_document_provider(self):
        return CouchDocumentProvider(self.iteration_key, self.doc_types)

    def _get_progress_logger(self):
        return CouchProcessorProgressLogger(self.doc_types)


class ExportByDomain(Migrator):
    domain = None

    def by_domain(self, domain):
        self.domain = domain
        self.iteration_key = self.iteration_key + '/domain=' + self.domain

    def migrate(self, filename=None, reset=False, max_retry=2, chunk_size=100):
        if not self.domain:
            raise MigrationError("Must specify domain")

        return super(ExportByDomain, self).migrate(
            filename=filename, reset=reset, max_retry=max_retry, chunk_size=chunk_size
        )

    def _get_document_provider(self):
        return CouchDocumentProvider(self.iteration_key, self.doc_types, domain=self.domain)

    def _get_doc_migrator(self, filename):
        return self.doc_migrator_class(self.slug, self.domain, self.couchdb)


class ExportMultimediaByDomain(ExportByDomain):
    def _get_document_provider(self):
        return CouchViewDocumentProvider(
            self.couchdb, self.iteration_key,
            "hqmedia/by_domain", view_keys=[self.domain]
        )


class SqlModelMigrator(Migrator):
    def __init__(self, slug, model_class, migrator_class):
        self.slug = slug
        self.model_class = model_class
        self.migrator_class = migrator_class

    def by_domain(self, domain):
        self.domain = domain

    def migrate(self, filename=None, reset=False, max_retry=2, chunk_size=100):
        from corehq.apps.dump_reload.sql.dump import get_all_model_querysets_for_domain
        from corehq.apps.dump_reload.sql.dump import allow_form_processing_queries

        if not self.domain:
            raise MigrationError("Must specify domain")

        if os.path.exists(get_export_filename(self.slug, self.domain)):
            raise MigrationError(
                "{} exporter doesn't support resume. "
                "To re-run the export use 'reset'".format(self.slug)
            )

        migrator = self.migrator_class(self.slug, self.domain)

        with migrator:
            with allow_form_processing_queries():
                for model_class, queryset in get_all_model_querysets_for_domain(self.model_class, self.domain):
                    for obj in queryset.iterator():
                        migrator.process_object(obj)
                        if migrator.total_blobs % chunk_size == 0:
                            print("Processed {} {} objects".format(migrator.total_blobs, self.slug))

        return migrator.total_blobs, 0


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
        ("HQSubmission", xform.XFormInstance),
    ], CouchAttachmentMigrator),
]}

EXPORTERS = {m.slug: m for m in [
    ExportByDomain("applications", [
        Application,
        RemoteApp,
        ("Application-Deleted", Application),
        ("RemoteApp-Deleted", RemoteApp),
    ], BlobDbBackendExporter),
    ExportMultimediaByDomain("multimedia", [
        hqmedia.CommCareMultimedia,
    ], BlobDbBackendExporter),
    ExportByDomain("couch_xforms", [
        xform.XFormInstance,
        ("XFormInstance-Deleted", xform.XFormInstance),
        xform.XFormArchived,
        xform.XFormDeprecated,
        xform.XFormDuplicate,
        xform.XFormError,
        xform.SubmissionErrorLog,
        ("HQSubmission", xform.XFormInstance),
    ], BlobDbBackendExporter),
    SqlModelMigrator(
        "sql_xforms",
        sql_xform.XFormAttachmentSQL,
        SqlFormAttachmentExporter
    ),
    ExportByDomain("saved_exports", [
        exports.CaseExportInstance,
        exports.FormExportInstance,
    ], BlobDbBackendExporter),
    SqlModelMigrator(
        "demo_user_restores",
        DemoUserRestore,
        DemoUserRestoreExporter
    )
]}


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
        for doc_type, model_class in doc_type_tuples_to_dict(migrator.doc_types).items():
            total += get_doc_count_by_type(model_class.get_db(), doc_type)
        if total > 500:
            message = MIGRATION_INSTRUCTIONS.format(slug=slug, total=total)
            raise MigrationNotComplete(message)

        # just do the migration if the number of documents is small
        migrated, skipped = migrator.migrate()
        if skipped:
            raise MigrationNotComplete(DOCS_SKIPPED_WARNING.format(skipped))

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
