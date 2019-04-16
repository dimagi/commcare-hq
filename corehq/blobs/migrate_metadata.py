from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from functools import partial
from itertools import groupby

import six
from couchdbkit import ResourceNotFound
from django.db import connections

from corehq.apps.domain import SHARED_DOMAIN, UNKNOWN_DOMAIN
from corehq.blobs import CODES
from corehq.blobs.mixin import BlobHelper, BlobMetaRef
from corehq.blobs.models import BlobMigrationState
from corehq.form_processor.backends.sql.dbaccessors import ReindexAccessor
from corehq.sql_db.util import get_db_alias_for_partitioned_doc
from corehq.util.doc_processor.sql import SqlDocumentProvider

import corehq.apps.accounting.models as acct
import corehq.apps.app_manager.models as apps
import corehq.apps.hqmedia.models as hqmedia
from corehq.apps.builds.models import CommCareBuild
from corehq.apps.case_importer.tracking.models import CaseUploadFileMeta, CaseUploadRecord
from corehq.apps.domain.models import Domain
from corehq.apps.export import models as exports
from corehq.apps.ota.models import DemoUserRestore
from corehq.apps.users.models import CommCareUser

import casexml.apps.case.models as cases
import couchforms.models as xform
from custom.icds_reports.models.helper import IcdsFile


class MultiDbMigrator(object):

    def __init__(self, slug, couch_types, sql_reindexers):

        self.slug = slug
        self.couch_types = couch_types
        self.sql_reindexers = sql_reindexers

    def iter_migrators(self):
        from . import migrate as mod
        NoStateMigrator, SqlMigrator, BlobMetaMigrator = make_migrators(mod)
        couch_migrator = partial(BlobMetaMigrator, blob_helper=couch_blob_helper)

        def db_key(doc_type):
            if isinstance(doc_type, tuple):
                doc_type = doc_type[1]
            return doc_type.get_db().dbname

        for key, types in groupby(sorted(self.couch_types, key=db_key), key=db_key):
            slug = "%s-%s" % (self.slug, key)
            yield NoStateMigrator(slug, list(types), couch_migrator)

        for rex in self.sql_reindexers:
            slug = "%s-%s" % (self.slug, rex.model_class.__name__)
            yield SqlMigrator(slug, rex(), BlobMetaMigrator)

    def migrate(self, filename, *args, **kw):
        def filen(n):
            return None if filename is None else "{}.{}".format(filename, n)
        migrated = 0
        skipped = 0
        for n, item in enumerate(self.iter_migrators()):
            one_migrated, one_skipped = item.migrate(filen(n), *args, **kw)
            migrated += one_migrated
            skipped += one_skipped
            print("\n")
        if not skipped:
            BlobMigrationState.objects.get_or_create(slug=self.slug)[0].save()
        return migrated, skipped


def make_migrators(mod):
    # defer class definitions to work around circular import

    class BlobMetaMigrator(mod.BaseDocMigrator):
        """Migrate blob metadata to BlobMeta model"""

        def __init__(self, *args, **kw):
            super(BlobMetaMigrator, self).__init__(*args, **kw)
            self.total_blobs = 0

        def migrate(self, doc):
            if not doc.get("external_blobs"):
                return True
            type_code = self.get_type_code(doc)
            obj = self.blob_helper(doc, self.couchdb, type_code)
            db = get_db_alias_for_partitioned_doc(doc["_id"])
            domain = obj.domain
            if domain is None:
                self.error(obj, {
                    "error": "unknown-domain",
                    "doc_type": obj.doc_type,
                    "doc_id": obj._id,
                })
                domain = UNKNOWN_DOMAIN
            if getattr(obj, "_attachments", None):
                self.error(obj, {
                    "error": "ignored-couch-attachments",
                    "doc_type": obj.doc_type,
                    "doc_id": obj._id,
                    "domain": obj.domain,
                    "attachments": obj._attachments,
                })
            with connections[db].cursor() as cursor:
                for name, meta in six.iteritems(obj.external_blobs):
                    if meta.blobmeta_id is not None:
                        # blobmeta already saved
                        continue
                    cursor.execute("""
                        INSERT INTO blobs_blobmeta (
                            domain,
                            type_code,
                            parent_id,
                            name,
                            key,
                            content_type,
                            content_length,
                            created_on
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, CLOCK_TIMESTAMP())
                        ON CONFLICT (key) DO NOTHING
                    """, params=[
                        domain,
                        type_code,
                        doc["_id"],
                        name,
                        meta.key,
                        meta.content_type,
                        meta.content_length or 0,
                    ])
                    self.total_blobs += 1
            return True

        def error(self, obj, doc):
            print("Error: %s %r" % (doc["error"], obj))
            super(BlobMetaMigrator, self).write_backup(doc)

    class NoStateMigrator(mod.Migrator):

        def write_migration_completed_state(self):
            pass

    class SqlMigrator(NoStateMigrator):

        def __init__(self, slug, reindexer, doc_migrator_class):
            types = [reindexer.model_class]

            def doc_migrator(*args, **kw):
                kw["blob_helper"] = reindexer.blob_helper
                kw["get_type_code"] = reindexer.get_type_code
                return doc_migrator_class(*args, **kw)

            super(SqlMigrator, self).__init__(slug, types, doc_migrator)
            self.reindexer = reindexer

        def get_document_provider(self):
            return SqlDocumentProvider(self.iteration_key, self.reindexer)

    return NoStateMigrator, SqlMigrator, BlobMetaMigrator


class SqlBlobHelper(object):
    """Adapt a SQL model object to look like a BlobHelper

    This is currently built on the assumtion that the SQL model only
    references a single blob, and the blob name is not used.
    """

    def __init__(self, obj, key, domain, reindexer):
        self.obj = obj
        self.domain = domain
        self.blobs = {"": BlobMetaRef(key=key, **reindexer.blob_kwargs(obj))}
        self.external_blobs = self.blobs

    def __repr__(self):
        return "<%s %s domain=%s id=%s>" % (
            type(self).__name__,
            self.doc_type,
            self.domain,
            self._id,
        )

    @property
    def _id(self):
        # NOTE unlike couch documents, this is different from `doc["_id"]`,
        # the value used to set `BlobMeta.parent_id`. This value should
        # only be used to identify the record in in case of error.
        return self.obj.id

    @property
    def doc_type(self):
        return type(self.obj).__name__


def sql_blob_helper(key_attr):

    def blob_helper(self, doc, *ignored):
        """This has the same signature as BlobHelper

        :returns: Object having parts of BlobHelper interface needed
        for blob migrations (currently only used by BlobMetaMigrator).
        """
        obj = doc["_obj_not_json"]
        domain = self.get_domain(obj)
        return SqlBlobHelper(obj, getattr(obj, key_attr), domain, self)

    return blob_helper


class PkReindexAccessor(ReindexAccessor):
    @property
    def id_field(self):
        return 'id'

    def get_doc(self, *args, **kw):
        # only used for retries; BlobMetaMigrator doesn't retry
        raise NotImplementedError

    def doc_to_json(self, obj, id):
        return {"_id": str(id), "_obj_not_json": obj, "external_blobs": True}


class CaseUploadFileMetaReindexAccessor(PkReindexAccessor):
    model_class = CaseUploadFileMeta
    blob_helper = sql_blob_helper("identifier")

    def doc_to_json(self, obj):
        return PkReindexAccessor.doc_to_json(self, obj, self.get_domain(obj))

    @staticmethod
    def get_type_code(doc):
        return CODES.data_import

    def get_domain(self, obj):
        try:
            return CaseUploadRecord.objects.get(upload_file_meta_id=obj.id).domain
        except CaseUploadRecord.DoesNotExist:
            return None

    def blob_kwargs(self, obj):
        return {"content_length": obj.length}


class DemoUserRestoreReindexAccessor(PkReindexAccessor):
    model_class = DemoUserRestore
    blob_helper = sql_blob_helper("restore_blob_id")

    def doc_to_json(self, obj):
        return PkReindexAccessor.doc_to_json(
            self, obj, obj.demo_user_id or "DemoUserRestore")

    @staticmethod
    def get_type_code(doc):
        return CODES.demo_user_restore

    def get_domain(self, obj):
        try:
            return CommCareUser.get(obj.demo_user_id).domain
        except ResourceNotFound:
            return None

    def blob_kwargs(self, obj):
        return {"content_length": obj.content_length, "content_type": "text/xml"}


class IcdsFileReindexAccessor(PkReindexAccessor):
    model_class = IcdsFile
    blob_helper = sql_blob_helper("blob_id")

    def doc_to_json(self, obj):
        return PkReindexAccessor.doc_to_json(self, obj, "IcdsFile")

    @staticmethod
    def get_type_code(doc):
        return CODES.tempfile

    def get_domain(self, obj):
        return "icds-cas"

    def blob_kwargs(self, obj):
        return {"content_length": 0}  # unknown content length


def couch_blob_helper(doc, *args, **kw):
    obj = BlobHelper(doc, *args, **kw)
    get_domain = DOMAIN_MAP.get(obj.doc_type)
    if get_domain is not None:
        assert not hasattr(obj, "domain"), obj
        obj.domain = get_domain(doc)
    elif not hasattr(obj, "domain"):
        obj.domain = None  # will trigger "unknown-domain" error
    return obj


def get_shared_domain(doc):
    return SHARED_DOMAIN


def get_invoice_domain(doc):
    if doc.get("is_wire"):
        try:
            return acct.WireInvoice.objects.get(id=int(doc["invoice_id"])).domain
        except acct.WireInvoice.DoesNotExist:
            return None  # trigger "unknown-domain" error
    # customer invoice has no domain
    return UNKNOWN_DOMAIN


DOMAIN_MAP = {
    "InvoicePdf": get_invoice_domain,
    "CommCareBuild": get_shared_domain,
    "CommCareAudio": get_shared_domain,
    "CommCareImage": get_shared_domain,
    "CommCareVideo": get_shared_domain,
    "CommCareMultimedia": get_shared_domain,
}


migrate_metadata = MultiDbMigrator("migrate_metadata",
    couch_types=[
        apps.Application,
        apps.LinkedApplication,
        apps.RemoteApp,
        ("Application-Deleted", apps.Application),
        ("RemoteApp-Deleted", apps.RemoteApp),
        apps.SavedAppBuild,
        CommCareBuild,
        Domain,
        acct.InvoicePdf,
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
        exports.SMSExportInstance,
    ],
    sql_reindexers=[
        CaseUploadFileMetaReindexAccessor,
        DemoUserRestoreReindexAccessor,
        IcdsFileReindexAccessor,
    ],
)
