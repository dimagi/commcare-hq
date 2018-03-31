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
   b. Add `_migrating_blobs_from_couch = True` to the class.
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

5. Remove `_migrating_blobs_from_couch = True` from each of your
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
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
import traceback
from abc import abstractmethod
from base64 import b64encode
from functools import partial
from itertools import groupby
from tempfile import mkdtemp

from django.conf import settings

from corehq.apps.accounting.models import InvoicePdf
from corehq.apps.export import models as exports
from corehq.apps.ota.models import DemoUserRestore
from corehq.blobs import get_blob_db, DEFAULT_BUCKET, BlobInfo
from corehq.blobs.exceptions import NotFound
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.mixin import BlobHelper, BlobMeta
from corehq.blobs.models import BlobMigrationState
from corehq.blobs.zipdb import get_export_filename
from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type
from corehq.util.doc_processor.couch import (
    CouchDocumentProvider, doc_type_tuples_to_dict, CouchViewDocumentProvider
)
from corehq.util.doc_processor.couch import CouchProcessorProgressLogger
from corehq.util.doc_processor.sql import SqlDocumentProvider
from corehq.util.doc_processor.interface import (
    BaseDocProcessor, DOCS_SKIPPED_WARNING,
    DocumentProcessorController
)
from couchdbkit import ResourceConflict
from corehq.form_processor.backends.sql.dbaccessors import ReindexAccessor

# models to be migrated
import corehq.apps.hqmedia.models as hqmedia
import couchforms.models as xform
import casexml.apps.case.models as cases
import corehq.apps.app_manager.models as apps
from corehq.apps.case_importer.tracking.filestorage import BUCKET as CASE_UPLOAD_BUCKET
from corehq.apps.case_importer.tracking.models import CaseUploadFileMeta
from couchexport.models import SavedBasicExport
import corehq.form_processor.models as sql_xform
import six

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
    if isinstance(data, six.text_type):
        data = data.encode("utf-8")
    return b64encode(data)


class BaseDocMigrator(BaseDocProcessor):

    # If true, load attachment content before migrating.
    load_attachments = False

    def __init__(self, slug, couchdb, filename=None, blob_helper=BlobHelper,
                 complete_migration=True):
        super(BaseDocMigrator, self).__init__()
        self.slug = slug
        self.couchdb = couchdb
        self.dirpath = None
        self.filename = filename
        self.blob_helper = blob_helper
        self.complete_migration = complete_migration
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
            obj = self.blob_helper(doc, self.couchdb)
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

        if not skipped and self.complete_migration:
            BlobMigrationState.objects.get_or_create(slug=self.slug)[0].save()


class CouchAttachmentMigrator(BaseDocMigrator):

    load_attachments = True

    def _do_migration(self, doc):
        attachments = doc.pop("_attachments")
        external_blobs = doc.setdefault("external_blobs", {})
        obj = self.blob_helper(doc, self.couchdb)
        try:
            with obj.atomic_blobs():
                for name, data in list(six.iteritems(attachments)):
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
    """Migrate blobs from one blob db to another

    The backup log for this migrator will contain one JSON object
    for each blob that was not found in the old blob db.
    """

    def __init__(self, *args, **kw):
        super(BlobDbBackendMigrator, self).__init__(*args, **kw)
        self.db = get_blob_db()
        self.total_blobs = 0
        self.not_found = 0
        self.bad_blobs_state = 0
        if not isinstance(self.db, MigratingBlobDB):
            raise MigrationError(
                "Expected to find migrating blob db backend (got %r)" % self.db)

    def _backup_doc(self, doc):
        pass

    def _do_migration(self, doc):
        obj = self.blob_helper(doc, self.couchdb)
        bucket = obj._blobdb_bucket()
        if obj.external_blobs != obj.blobs:
            self.bad_blobs_state += 1
            super(BlobDbBackendMigrator, self)._backup_doc({
                "doc_type": obj.doc_type,
                "doc_id": obj._id,
                "error": "blobs != external_blobs",
            })
        for name, meta in six.iteritems(obj.external_blobs):
            self.total_blobs += 1
            try:
                content = self.db.old_db.get(meta.id, bucket)
            except NotFound:
                if not self.db.new_db.exists(meta.id, bucket):
                    super(BlobDbBackendMigrator, self)._backup_doc({
                        "doc_type": obj.doc_type,
                        "doc_id": obj._id,
                        "blob_identifier": meta.id,
                        "blob_bucket": bucket,
                        "error": "not found",
                    })
                    self.not_found += 1
            else:
                with content:
                    self.db.copy_blob(content, meta.info, bucket)
        return True

    def processing_complete(self, skipped):
        super(BlobDbBackendMigrator, self).processing_complete(skipped)
        if self.not_found:
            print(PROCESSING_COMPLETE_MESSAGE.format(self.not_found, self.total_blobs))
            if self.dirpath is None:
                print("Missing blob ids have been written in the log file:")
                print(self.filename)
        if self.bad_blobs_state:
            print("{count} documents had `blobs != external_blobs`, which is "
                  "not a valid state. Search for 'blobs != external_blobs' in "
                  "the migration logs to find them."
                  .format(count=self.bad_blobs_state))

    def should_process(self, doc):
        return self.blob_helper.get_external_blobs(doc)


class BlobDbBackendExporter(BaseDocProcessor):

    def __init__(self, slug, domain, couchdb, blob_helper=BlobHelper):
        from corehq.blobs.zipdb import ZipBlobDB
        self.slug = slug
        self.blob_helper = blob_helper
        self.db = ZipBlobDB(self.slug, domain)
        self.total_blobs = 0
        self.not_found = 0
        self.domain = domain
        self.couchdb = couchdb

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

    def process_doc(self, doc):
        obj = self.blob_helper(doc, self.couchdb)
        bucket = obj._blobdb_bucket()
        assert obj.external_blobs and obj.external_blobs == obj.blobs, doc
        from_db = get_blob_db()
        for name, meta in six.iteritems(obj.blobs):
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
        return self.blob_helper.get_external_blobs(doc)


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


class SqlBlobHelper(object):
    """Adapt a SQL model object to look like a BlobHelper

    This is currently built on the assumtion that the SQL model only
    references a single blob, and the blob name is not used.
    """

    def __init__(self, obj, blob_id, bucket):
        self.obj = obj
        self.blobs = {"name-ignored": BlobMeta(id=blob_id)}
        self.external_blobs = self.blobs
        self._blobdb_bucket = lambda: bucket

    @property
    def _id(self):
        return self.obj.id

    @property
    def doc_type(self):
        return type(self.obj).__name__


def sql_blob_helper(id_attr, bucket):
    get_bucket = bucket if hasattr(bucket, "__call__") else (lambda obj: bucket)

    def blob_helper(doc, couchdb_ignored=None):
        """This has the same signature as BlobHelper

        :returns: Object having parts of BlobHelper interface needed
        for blob migrations (currently only used by BlobDbBackendMigrator).
        """
        obj = doc["_obj_not_json"]
        blob_id = getattr(obj, id_attr)
        bucket = get_bucket(obj)
        return SqlBlobHelper(obj, blob_id, bucket)

    blob_helper.id_attr = id_attr

    # HACK this is only ever used to determine if there are blobs
    # to migrate. For SQL objects there always will be.
    blob_helper.get_external_blobs = lambda doc: True

    return staticmethod(blob_helper)


class PkReindexAccessor(ReindexAccessor):
    @property
    def id_field(self):
        return 'id'

    def get_doc(self, *args, **kw):
        # only used for retries; BlobDbBackendMigrator doesn't retry
        raise NotImplementedError

    def doc_to_json(self, obj):
        return {"_id": obj.id, "_obj_not_json": obj}


class CaseUploadFileMetaReindexAccessor(PkReindexAccessor):
    model_class = CaseUploadFileMeta
    blob_helper = sql_blob_helper("identifier", CASE_UPLOAD_BUCKET)


class CaseAttachmentSQLReindexAccessor(PkReindexAccessor):
    model_class = sql_xform.CaseAttachmentSQL
    blob_helper = sql_blob_helper("blob_id", lambda obj: obj.blobdb_bucket())


class XFormAttachmentSQLReindexAccessor(PkReindexAccessor):
    model_class = sql_xform.XFormAttachmentSQL
    blob_helper = sql_blob_helper("blob_id", lambda obj: obj.blobdb_bucket())


class DemoUserRestoreReindexAccessor(PkReindexAccessor):
    model_class = DemoUserRestore
    blob_helper = sql_blob_helper("restore_blob_id", DEFAULT_BUCKET)


class Migrator(object):

    def __init__(self, slug, doc_types, doc_migrator_class):
        self.slug = slug
        self.doc_migrator_class = doc_migrator_class
        self.doc_types = doc_types
        first_type = doc_types[0]
        first_type = (first_type[0] if isinstance(first_type, tuple) else first_type)
        self.couchdb = first_type.get_db() if hasattr(first_type, "get_db") else None

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


class SqlMigrator(Migrator):

    def __init__(self, slug, reindexer, doc_migrator_class):
        types = [reindexer.model_class]
        assert not hasattr(types[0], "get_db"), types[0]  # not a couch model
        doc_migrator = partial(doc_migrator_class, blob_helper=reindexer.blob_helper)
        super(SqlMigrator, self).__init__(slug, types, doc_migrator)
        self.reindexer = reindexer

    def _get_document_provider(self):
        return SqlDocumentProvider(self.iteration_key, self.reindexer)


class MultiDbMigrator(object):

    def __init__(self, slug, couch_types, sql_reindexers, doc_migrator_class):
        self.slug = slug
        self.migrators = migrators = []
        doc_migrator = partial(doc_migrator_class, complete_migration=False)

        def db_key(doc_type):
            if isinstance(doc_type, tuple):
                doc_type = doc_type[1]
            return doc_type.get_db().dbname

        for key, types in groupby(sorted(couch_types, key=db_key), key=db_key):
            migrators.append(Migrator(slug, list(types), doc_migrator))

        for rex in sql_reindexers:
            migrators.append(SqlMigrator(slug, rex(), doc_migrator))

    def migrate(self, filename, *args, **kw):
        def filen(n):
            return None if filename is None else "{}.{}".format(filename, n)
        migrated = 0
        skipped = 0
        for n, item in enumerate(self.migrators):
            one_migrated, one_skipped = item.migrate(filen(n), *args, **kw)
            migrated += one_migrated
            skipped += one_skipped
            print("\n")
        if not skipped:
            BlobMigrationState.objects.get_or_create(slug=self.slug)[0].save()
        return migrated, skipped


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

    def migrate(self, filename=None, reset=False, max_retry=2, chunk_size=100, limit_to_db=None):
        from corehq.apps.dump_reload.sql.dump import get_all_model_iterators_builders_for_domain

        if not self.domain:
            raise MigrationError("Must specify domain")

        if os.path.exists(get_export_filename(self.slug, self.domain)):
            raise MigrationError(
                "{} exporter doesn't support resume. "
                "To re-run the export use 'reset'".format(self.slug)
            )

        migrator = self.migrator_class(self.slug, self.domain)

        with migrator:
            builders = get_all_model_iterators_builders_for_domain(self.model_class, self.domain, limit_to_db)
            for model_class, builder in builders:
                for iterator in builder.iterators():
                    for obj in iterator:
                        migrator.process_object(obj)
                        if migrator.total_blobs % chunk_size == 0:
                            print("Processed {} {} objects".format(migrator.total_blobs, self.slug))

        return migrator.total_blobs, 0


MIGRATIONS = {m.slug: m for m in [
    Migrator('invoice_pdfs', [InvoicePdf], CouchAttachmentMigrator),
    Migrator("saved_exports", [SavedBasicExport], CouchAttachmentMigrator),
    Migrator("applications", [
        apps.Application,
        apps.RemoteApp,
        ("Application-Deleted", apps.Application),
        ("RemoteApp-Deleted", apps.RemoteApp),
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
    Migrator("cases", [
        cases.CommCareCase,
        ('CommCareCase-deleted', cases.CommCareCase),
        ('CommCareCase-Deleted', cases.CommCareCase),
        ('CommCareCase-Deleted-Deleted', cases.CommCareCase),
    ], CouchAttachmentMigrator),
    MultiDbMigrator("migrate_backend",
        couch_types=[
            apps.Application,
            apps.LinkedApplication,
            apps.RemoteApp,
            #SavedAppBuild, # do we need to migrate these? (none in couch on prod)
            ("Application-Deleted", apps.Application),
            ("RemoteApp-Deleted", apps.RemoteApp),
            SavedBasicExport,
            hqmedia.CommCareAudio,
            hqmedia.CommCareImage,
            hqmedia.CommCareVideo,
            hqmedia.CommCareMultimedia,
            xform.XFormInstance,
            ("XFormInstance-Deleted", xform.XFormInstance),
            xform.XFormArchived,
            xform.XFormDeprecated,
            xform.XFormDuplicate,
            xform.XFormError,
            xform.SubmissionErrorLog,
            ("HQSubmission", xform.XFormInstance),
            cases.CommCareCase,
            ('CommCareCase-deleted', cases.CommCareCase),
            ('CommCareCase-Deleted', cases.CommCareCase),
            ('CommCareCase-Deleted-Deleted', cases.CommCareCase),
            exports.CaseExportInstance,
            exports.FormExportInstance,
        ],
        sql_reindexers=[
            CaseUploadFileMetaReindexAccessor,
            CaseAttachmentSQLReindexAccessor,
            XFormAttachmentSQLReindexAccessor,
            DemoUserRestoreReindexAccessor,
        ],
        doc_migrator_class=BlobDbBackendMigrator,
    ),
]}

EXPORTERS = {m.slug: m for m in [
    ExportByDomain("applications", [
        apps.Application,
        apps.RemoteApp,
        ("Application-Deleted", apps.Application),
        ("RemoteApp-Deleted", apps.RemoteApp),
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
