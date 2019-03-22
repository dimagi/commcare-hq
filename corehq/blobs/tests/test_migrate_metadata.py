# coding=utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from itertools import chain
from os.path import join

import corehq.blobs.migrate_metadata as mod
from corehq.blobs import CODES
from corehq.blobs.migrate import MIGRATIONS
from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.test_migrate import discard_migration_state

from corehq.sql_db.util import get_db_alias_for_partitioned_doc

import attr
from dimagi.ext.couchdbkit import DocumentSchema, IntegerProperty, StringProperty
from django.test import TestCase
from testil import tempdir


class TestMigrateBackend(TestCase):

    longMessage = True
    slug = "migrate_metadata"
    couch_doc_types = {
        "Application": mod.apps.Application,
        "LinkedApplication": mod.apps.LinkedApplication,
        "RemoteApp": mod.apps.RemoteApp,
        "Application-Deleted": mod.apps.Application,
        "RemoteApp-Deleted": mod.apps.RemoteApp,
        "SavedAppBuild": mod.apps.SavedAppBuild,
        "CommCareBuild": mod.CommCareBuild,
        "Domain": mod.Domain,
        "InvoicePdf": mod.acct.InvoicePdf,
        "CommCareAudio": mod.hqmedia.CommCareAudio,
        "CommCareImage": mod.hqmedia.CommCareImage,
        "CommCareVideo": mod.hqmedia.CommCareVideo,
        "CommCareMultimedia": mod.hqmedia.CommCareMultimedia,
        "XFormInstance": mod.xform.XFormInstance,
        "XFormInstance-Deleted": mod.xform.XFormInstance,
        "XFormArchived": mod.xform.XFormArchived,
        "XFormDeprecated": mod.xform.XFormDeprecated,
        "XFormDuplicate": mod.xform.XFormDuplicate,
        "XFormError": mod.xform.XFormError,
        "SubmissionErrorLog": mod.xform.SubmissionErrorLog,
        "HQSubmission": mod.xform.XFormInstance,
        "CommCareCase": mod.cases.CommCareCase,
        'CommCareCase-deleted': mod.cases.CommCareCase,
        'CommCareCase-Deleted': mod.cases.CommCareCase,
        'CommCareCase-Deleted-Deleted': mod.cases.CommCareCase,
        "CaseExportInstance": mod.exports.CaseExportInstance,
        "FormExportInstance": mod.exports.FormExportInstance,
        "SMSExportInstance": mod.exports.SMSExportInstance,
    }
    shared_domain_doc_types = {
        "CommCareBuild",
        "CommCareAudio",
        "CommCareImage",
        "CommCareVideo",
        "CommCareMultimedia",
    }
    sql_reindex_accessors = [
        mod.CaseUploadFileMetaReindexAccessor,
        mod.DemoUserRestoreReindexAccessor,
        mod.IcdsFileReindexAccessor,
    ]

    @classmethod
    def setUpClass(cls):
        super(TestMigrateBackend, cls).setUpClass()
        cls.user = mod.CommCareUser(username="testuser", domain="test")
        cls.user.save()
        assert cls.user._id, cls.user

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        super(TestMigrateBackend, cls).tearDownClass()

    def CaseUploadFileMeta_save(self, obj, key):
        obj.identifier = key
        obj.filename = "file.txt"
        obj.length = 15
        obj.save()
        mod.CaseUploadRecord.objects.create(
            domain="test",
            upload_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            couch_user_id=self.user._id,
            case_type="test",
            upload_file_meta=obj,
        )
        return SqlDoc(obj, "test", "test", CODES.data_import, None, 15)

    def DemoUserRestore_save(self, obj, key):
        obj.restore_blob_id = key
        obj.demo_user_id = uid = self.user._id
        obj.content_length = 87
        obj.save()
        code = CODES.demo_user_restore
        return SqlDoc(obj, self.user.domain, uid, code, "text/xml", 87)

    def IcdsFile_save(self, obj, key):
        obj.blob_id = key
        obj.data_type = "unknown"
        obj.save()
        return SqlDoc(obj, "icds-cas", "IcdsFile", CODES.tempfile, None, 0)

    def setUp(self):
        super(TestMigrateBackend, self).setUp()

        self.not_founds = set()
        self.couch_docs = []
        for doc_type, doc_class in self.couch_doc_types.items():
            obj = doc_class()
            if hasattr(doc_class, "domain"):
                domain = obj.domain = "test"
            elif doc_class is mod.Domain:
                domain = obj.name = "test"
            elif doc_type in self.shared_domain_doc_types:
                domain = mod.SHARED_DOMAIN
            else:
                domain = mod.UNKNOWN_DOMAIN
            obj.doc_type = doc_type
            doc = obj.to_json()
            doc["external_blobs"] = {"blob": OldCouchBlobMeta(
                id=doc_type.lower(),
                content_type="text/plain",
                content_length=7,
            ).to_json()}
            doc_class.get_db().save_doc(doc)
            self.couch_docs.append(CouchDoc(doc_class, doc_type, domain, doc))

        def create_sql_doc(rex):
            key = uuid.uuid4().hex
            obj = rex.model_class()
            save_attr = rex.model_class.__name__ + "_save"
            return getattr(self, save_attr)(obj, key)
        self.sql_docs = []
        for rex in (x() for x in self.sql_reindex_accessors):
            self.sql_docs.append(create_sql_doc(rex))

        self.test_size = len(self.couch_docs) + len(self.sql_docs)
        discard_migration_state(self.slug)

    def tearDown(self):
        try:
            for doc in self.couch_docs:
                doc.class_.get_db().delete_doc(doc.id)
            for doc in self.sql_docs:
                doc.obj.delete()
            discard_migration_state(self.slug)
        finally:
            super(TestMigrateBackend, self).tearDown()

    def test_migrate_backend(self):
        with tempdir() as tmp:
            filename = join(tmp, "file.txt")
            # do migration
            migrated, skipped = MIGRATIONS[self.slug].migrate(filename)
            self.assertGreaterEqual(migrated, self.test_size)

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=self.slug)

        # verify: metadata was saved in BlobMeta table

        for doc in self.couch_docs:
            obj = doc.class_.get(doc.id)
            self.assertEqual(obj._rev, doc.data["_rev"])  # rev should not change
            self.assertEqual(set(obj.blobs), set(doc.data["external_blobs"]))
            db = get_db_alias_for_partitioned_doc(obj._id)
            metas = {meta.name: meta
                for meta in BlobMeta.objects.using(db).filter(parent_id=doc.id)}
            for name, meta in obj.blobs.items():
                blobmeta = metas[name]
                dbname = doc.class_.get_db().dbname
                key = "%s/%s/%s" % (dbname, obj._id, doc.doc_type.lower())
                self.assertEqual(blobmeta.key, key, doc)
                self.assertEqual(blobmeta.domain, doc.domain, doc)
                self.assertEqual(blobmeta.content_type, meta.content_type, doc)
                self.assertEqual(blobmeta.content_length, meta.content_length, doc)

        for doc in self.sql_docs:
            db = get_db_alias_for_partitioned_doc(doc.parent_id)
            blobmeta = BlobMeta.objects.using(db).get(
                parent_id=doc.parent_id,
                type_code=doc.type_code,
                name="",
            )
            self.assertEqual(blobmeta.domain, doc.domain, doc)
            self.assertEqual(blobmeta.content_type, doc.content_type, doc)
            self.assertEqual(blobmeta.content_length, doc.content_length, doc)

    def test_resume_migration(self):
        with tempdir() as tmp:
            filename = join(tmp, "file.txt")
            migrator = MIGRATIONS[self.slug]
            migrated1, skipped = migrator.migrate(filename)
            self.assertGreaterEqual(migrated1, self.test_size)
            self.assertFalse(skipped)

            # discard state to simulate interrupted migration
            for mig in migrator.iter_migrators():
                mig.get_document_provider().get_document_iterator(1).discard_state()

            # resumed migration: all docs already migrated, so BlobMeta records
            # exist, but should not cause errors on attempting to insert them
            migrated2, skipped = MIGRATIONS[self.slug].migrate(filename)
            self.assertEqual(migrated1, migrated2)
            self.assertFalse(skipped)

            mod.BlobMigrationState.objects.get(slug=self.slug)

        parent_ids = chain(
            (doc.id for doc in self.couch_docs),
            (doc.parent_id for doc in self.sql_docs),
        )

        # should have one blob per parent
        for parent_id in parent_ids:
            db = get_db_alias_for_partitioned_doc(parent_id)
            metas = list(BlobMeta.objects.using(db).filter(parent_id=parent_id))
            self.assertEqual(len(metas), 1, metas)


def resurrect_old_couch_blob_meta():

    class BlobMeta(DocumentSchema):
        id = StringProperty()
        content_type = StringProperty()
        content_length = IntegerProperty()
        digest = StringProperty()

    return BlobMeta


OldCouchBlobMeta = resurrect_old_couch_blob_meta()


@attr.s
class CouchDoc(object):
    """Container for items in TestMigrateBackend.couch_docs"""
    class_ = attr.ib()
    doc_type = attr.ib()
    domain = attr.ib()
    data = attr.ib()

    @property
    def id(self):
        return self.data["_id"]


@attr.s
class SqlDoc(object):
    """Container for items in TestMigrateBackend.sql_docs"""
    obj = attr.ib()
    domain = attr.ib()
    parent_id = attr.ib()
    type_code = attr.ib()
    content_type = attr.ib()
    content_length = attr.ib()
