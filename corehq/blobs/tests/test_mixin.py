from __future__ import unicode_literals
from __future__ import absolute_import
import os
import uuid
from base64 import b64encode
from copy import deepcopy
from hashlib import md5
from os.path import join
from io import BytesIO

from django.conf import settings
from django.test import TestCase

import corehq.blobs.mixin as mod
from corehq.blobs import CODES
from corehq.blobs.s3db import maybe_not_found
from corehq.blobs.tests.util import (TemporaryFilesystemBlobDB,
    TemporaryMigratingBlobDB, TemporaryS3BlobDB)
from corehq.blobs.util import ClosingContextProxy
from corehq.util.test_utils import generate_cases, trap_extra_setup
from dimagi.ext.couchdbkit import Document
from mock import patch
import six
from io import open


class BaseTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseTestCase, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(BaseTestCase, cls).tearDownClass()

    def make_doc(self, type_=None, id=None):
        if type_ is None:
            type_ = FakeCouchDocument
        if id is None:
            id = uuid.uuid4().hex
        return type_({"_id": id})

    def setUp(self):
        self.obj = self.make_doc()

    def get_blob(self, key):
        return self.TestBlob(self.db, key)

    class TestBlob(object):

        def __init__(self, db, key):
            self.key = key
            self.db = db
            self.path = db.get_path(key=key)

        def exists(self):
            return os.path.exists(self.path)

        def open(self):
            return open(self.path, 'rb')

        def listdir(self):
            path = self.path
            if "/" in self.key:
                assert path.endswith("/" + self.key), (path, self.key)
                path = path[:-len(self.key) - 1]
            else:
                path = os.path.dirname(path)
            return os.listdir(path)


class TestBlobMixin(BaseTestCase):

    def test_put_attachment_without_name(self):
        with self.assertRaises(mod.InvalidAttachment):
            self.obj.put_attachment("content")

    def test_put_attachment_for_doc_with_bad_path_id(self):
        obj = self.make_doc(id="uuid:some-random-value")
        name = "test.0"
        data = "\u4500 content"
        obj.put_attachment(data, name)
        self.assertEqual(obj.fetch_attachment(name).decode('utf-8'), data)

    def test_put_attachment_unicode(self):
        name = "test.1"
        data = "\u4500 content"
        self.obj.put_attachment(data, name)
        self.assertEqual(self.obj.fetch_attachment(name).decode('utf-8'), data)

    def test_put_attachment_bytes(self):
        name = "test.1"
        data = b"\xe4\x94 content"  # cannot be decoded as UTF-8
        self.obj.put_attachment(data, name)
        self.assertEqual(self.obj.fetch_attachment(name), data)

    def test_put_attachment_with_named_content(self):
        content = BytesIO(b"content")
        content.name = "test.1"
        self.obj.put_attachment(content)
        self.assertEqual(self.obj.fetch_attachment(content.name), b"content")
        self.assertTrue(self.obj.saved)

    def test_fetch_attachment_with_unicode(self):
        name = "test.1"
        content = "\u4500 is not ascii"
        self.obj.put_attachment(content, name)
        self.assertEqual(self.obj.fetch_attachment(name).decode('utf-8'), content)

    def test_fetch_attachment_stream(self):
        name = "test.1"
        content = "\u4500 is not ascii"
        self.obj.put_attachment(content, name)
        with self.obj.fetch_attachment(name, stream=True) as fh:
            self.assertEqual(fh.read().decode("utf-8"), content)

    def test_delete_attachment(self):
        name = "test.\u4500"
        content = "\u4500 is not ascii"
        self.obj.put_attachment(content, name)
        self.obj.saved = False
        self.obj.delete_attachment(name)
        self.assertTrue(self.obj.saved)
        with self.assertRaises(mod.ResourceNotFound):
            self.obj.fetch_attachment(name)

    def test_document_blobs(self):
        name = "test.1"
        content = BytesIO(b"content")
        self.obj.put_attachment(content, name, content_type="text/plain")
        self.assertEqual(self.obj.blobs[name].content_type, "text/plain")
        self.assertEqual(self.obj.blobs[name].content_length, 7)

    def test_deferred_put_attachment(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        content = BytesIO(b"content")
        obj.deferred_put_attachment(content, name, content_type="text/plain")
        self.assertEqual(obj.blobs[name].key, None)
        self.assertEqual(obj.blobs[name].content_type, "text/plain")
        self.assertEqual(obj.blobs[name].content_length, 7)
        self.assertFalse(obj.saved)

    def test_put_attachment_overwrites_unsaved_blob(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        obj.deferred_put_attachment(b"<xml />", name, content_type="text/xml")
        obj.put_attachment(b"new", name, content_type="text/plain")
        self.assertTrue(obj.blobs[name].key is not None)
        self.assertEqual(obj.blobs[name].content_type, "text/plain")
        self.assertEqual(obj.blobs[name].content_length, 3)

    def test_fetch_attachment_returns_unsaved_blob(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        content = b"<xml />"
        obj.deferred_put_attachment(content, name, content_type="text/xml")
        self.assertEqual(obj.fetch_attachment(name), content)

    def test_delete_attachment_deletes_unsaved_blob(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        content = b"<xml />"
        obj.deferred_put_attachment(content, name, content_type="text/xml")
        self.assertTrue(obj.delete_attachment(name))
        with self.assertRaises(mod.ResourceNotFound):
            self.obj.fetch_attachment(name)

    def test_deferred_delete_attachment(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        obj.put_attachment(b"new", name, content_type="text/plain")
        self.assertTrue(obj.blobs[name].key)
        obj.deferred_delete_attachment(name)
        self.assertNotIn(name, obj.blobs)
        self.assertNotIn(name, obj.persistent_blobs)
        self.assertIn(name, obj.external_blobs)
        obj.save()
        self.assertNotIn(name, obj.blobs)
        self.assertNotIn(name, obj.persistent_blobs)
        self.assertNotIn(name, obj.external_blobs)

    def test_fetch_attachment_after_deferred_delete_attachment(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        obj.put_attachment(b"new", name, content_type="text/plain")
        obj.deferred_delete_attachment(name)
        with self.assertRaises(mod.ResourceNotFound):
            obj.fetch_attachment(name)
        obj.save()
        self.assertFalse(obj._deferred_blobs)
        with self.assertRaises(mod.ResourceNotFound):
            obj.fetch_attachment(name)

    def test_persistent_blobs(self):
        content = b"<xml />"
        couch_digest = "md5-" + b64encode(md5(content).digest()).decode('utf-8')
        obj = self.make_doc(DeferredPutBlobDocument)
        obj._migrating_blobs_from_couch = True
        obj._attachments = {"couch": {
            "content_type": None,
            "digest": couch_digest,
            "length": 13,
        }}
        obj.put_attachment(content, "blobdb", content_type="text/plain")
        obj.put_attachment(content, "blobdb-deferred", content_type="text/plain")
        obj.deferred_put_attachment(content, "deferred", content_type="text/plain")
        obj.deferred_put_attachment(content, "blobdb-deferred", content_type="text/plain")
        self.assertEqual(set(obj.persistent_blobs), {"blobdb", "couch"})

    def test_save_persists_unsaved_blob(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        content = BytesIO(b"content")
        obj.deferred_put_attachment(content, name, content_type="text/plain")
        obj.save()
        self.assertTrue(obj.saved)
        self.assertTrue(obj.blobs[name].key is not None)
        self.assertEqual(obj.blobs[name].content_type, "text/plain")
        self.assertEqual(obj.blobs[name].content_length, 7)

    def test_blob_directory(self):
        name = join("commcarehq_test", self.obj._id, "test.1")
        content = BytesIO(b"test_blob_directory content")
        self.obj.put_attachment(content, name)
        blob = self.get_blob(self.obj.blobs[name].key)
        with blob.open() as fh:
            self.assertEqual(fh.read(), b"test_blob_directory content")

    def test_put_attachment_deletes_replaced_blob(self):
        name = "test.\u4500"
        self.obj.put_attachment("content 1", name)
        blob1 = self.get_blob(self.obj.blobs[name].key)
        self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].key)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected file: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), b"content 2")

    def test_put_attachment_failed_save_does_not_delete_replaced_blob(self):
        name = "test.\u4500"
        doc = self.make_doc(FailingSaveCouchDocument)
        doc.put_attachment("content 1", name)
        old_blob = doc.blobs[name]
        with self.assertRaises(BlowUp):
            doc.put_attachment("content 2", name)
        blob = self.get_blob(old_blob.key)
        doc.blobs[name] = old_blob  # simulate get from couch
        self.assertTrue(blob.exists(), "not found: " + blob.path)
        self.assertEqual(doc.fetch_attachment(name), b"content 1")

    def test_blobs_property(self):
        doc = self.make_doc(FallbackToCouchDocument)
        doc.put_attachment("content", "blob", content_type="text/plain")
        self.assertIn("blob", doc.blobs)
        self.assertEqual(doc.blobs["blob"].content_length, 7)

    def test_unsaved_document(self):
        obj = FakeCouchDocument()
        with self.assertRaises(mod.ResourceNotFound):
            obj.put_attachment(b"content", "test.1")

    def test_atomic_blobs_success(self):
        name = "test.1"
        _id = self.obj._id
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content", name)
        self.assertTrue(self.obj.saved)
        self.assertEqual(self.obj._id, _id)
        self.assertEqual(self.obj.fetch_attachment(name), b"content")
        self.assertIn(name, self.obj.blobs)

    def test_atomic_blobs_success_and_new_id(self):
        name = "test.1"
        obj = FakeCouchDocument()
        obj._id = None
        with obj.atomic_blobs():
            obj.put_attachment("content", name)
        self.assertTrue(obj.saved)
        self.assertTrue(obj._id is not None)
        self.assertEqual(obj.fetch_attachment(name), b"content")
        self.assertIn(name, obj.blobs)

    def test_atomic_blobs_deletes_replaced_blob(self):
        name = "test.\u4500"
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
        blob1 = self.get_blob(self.obj.blobs[name].key)
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].key)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected blob: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), b"content 2")

    def test_atomic_blobs_deletes_replaced_blob_in_same_context(self):
        name = "test.\u4500"
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
            blob1 = self.get_blob(self.obj.blobs[name].key)
            self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].key)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected blob: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), b"content 2")

    def test_atomic_blobs_deletes_replaced_blob_in_nested_context(self):
        name = "test.\u4500"
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
            blob1 = self.get_blob(self.obj.blobs[name].key)
            with self.obj.atomic_blobs():
                self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].key)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected blob: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), b"content 2")

    def test_atomic_blobs_preserves_blob_replaced_in_failed_nested_context(self):
        name = "test.\u4500"
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
            blob1 = self.get_blob(self.obj.blobs[name].key)
            with self.assertRaises(BlowUp):
                with self.obj.atomic_blobs():
                    self.obj.put_attachment("content 2", name)
                    blob2 = self.get_blob(self.obj.blobs[name].key)
                    raise BlowUp("fail")
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob2.exists(), "found unexpected blob: " + blob2.path)
        self.assertEqual(self.obj.fetch_attachment(name), b"content 1")

    def test_atomic_blobs_fail(self):
        name = "test.1"
        _id = self.obj._id
        with self.assertRaises(BlowUp):
            with self.obj.atomic_blobs():
                self.obj.put_attachment("content", name)
                raise BlowUp("while saving atomic blobs")
        self.assertFalse(self.obj.saved)
        self.assertEqual(self.obj._id, _id)
        with self.assertRaises(mod.ResourceNotFound):
            self.obj.fetch_attachment(name)
        self.assertNotIn(name, self.obj.blobs)

    def test_atomic_blobs_fail_does_not_delete_out_of_context_blobs(self):
        self.obj.put_attachment("content", "outside")
        with self.assertRaises(BlowUp):
            with self.obj.atomic_blobs():
                self.obj.put_attachment("content", "inside")
                raise BlowUp("while saving atomic blobs")
        self.assertEqual(set(self.obj.blobs), {"outside"})

    def test_atomic_blobs_fail_does_not_overwrite_existing_blob(self):
        name = "name"
        self.obj.put_attachment("content", name)
        blob_files = self.get_blob(self.obj.blobs[name].key).listdir()
        with self.assertRaises(BlowUp):
            with self.obj.atomic_blobs():
                self.obj.put_attachment("new content", name)
                raise BlowUp("while saving atomic blobs")
        self.assertEqual(self.obj.blobs[name].content_length, 7)
        self.assertEqual(self.obj.fetch_attachment(name), b"content")
        # verify cleanup
        blob = self.get_blob(self.obj.blobs[name].key)
        self.assertEqual(blob.listdir(), blob_files)

    def test_atomic_blobs_fail_restores_deleted_blob(self):
        name = "delete-fail"
        self.obj.put_attachment("content", name)
        blob = self.get_blob(self.obj.blobs[name].key)
        blob_files = blob.listdir()
        with self.assertRaises(BlowUp):
            with self.obj.atomic_blobs():
                self.obj.delete_attachment(name)
                raise BlowUp("while deleting blob")
        self.assertEqual(self.obj.blobs[name].content_length, 7)
        self.assertEqual(self.obj.fetch_attachment(name), b"content")
        # verify cleanup
        self.assertEqual(blob.listdir(), blob_files)

    def test_atomic_blobs_bug_deleting_existing_blob(self):
        self.obj.put_attachment("file content", "file")
        old_meta = self.obj.blobs["file"]
        saved = []

        def save():
            self.obj.save()
            assert self.obj.blobs["file"] is not old_meta
            saved.append(1)

        with self.obj.atomic_blobs(save):
            self.obj.put_attachment("new content", "new")
        self.assertTrue(saved)
        # bug caused old blobs (not modifed in atomic context) to be deleted
        self.assertEqual(self.obj.fetch_attachment("file"), b"file content")

    def test_atomic_blobs_bug_deleting_existing_blob_on_save_failure(self):
        self.obj.put_attachment("file content", "file")
        old_meta = self.obj.blobs["file"]

        def save():
            self.obj.save()
            assert self.obj.blobs["file"] is not old_meta
            raise BlowUp("boom!")

        with self.assertRaises(BlowUp):
            with self.obj.atomic_blobs(save):
                self.obj.put_attachment("new content", "new")
        self.assertNotIn("new", self.obj.blobs)
        # bug caused old blobs (not modifed in atomic context) to be deleted
        self.assertEqual(self.obj.fetch_attachment("file"), b"file content")

    def test_migrating_flag_not_in_doc_json(self):
        obj_type = type(self.obj)
        self.assertFalse(obj_type._migrating_blobs_from_couch)
        self.assertFalse(self.obj._migrating_blobs_from_couch)
        type_path = obj_type.__module__ + "." + obj_type.__name__
        with patch(type_path + "._migrating_blobs_from_couch", True, create=True):
            self.assertTrue(self.obj._migrating_blobs_from_couch)
            self.assertNotIn("_migrating_blobs_from_couch", self.obj.to_json())
        self.assertFalse(obj_type._migrating_blobs_from_couch)

        self.obj._migrating_blobs_from_couch = True
        self.assertNotIn("_migrating_blobs_from_couch", self.obj.to_json())

    def test_wrap_with_legacy_BlobMeta(self):
        obj = FakeCouchDocument.wrap({
            "doc_type": "FakeCouchDocument",
            "domain": "test",
            "_id": "abc123",
            "external_blobs": {
                "file.txt": {
                    "id": "blobid",
                    "content_type": "text/plain",
                    "content_length": 9,
                    "digest": "md5-PKF0bQ5Vl99sgbsjAnyNQA==",
                    "doc_type": "BlobMeta",
                },
            },
        })
        meta = obj.external_blobs["file.txt"]
        self.assertIsInstance(meta, mod.BlobMetaRef)
        self.assertEqual(meta.key, "commcarehq_test/abc123/blobid")
        with self.assertRaises(AttributeError):
            meta.id

    def test_wrap_with_bad_id(self):
        doc = {
            "_id": "uuid:9855adcb-da3a-41e2-afaf-71d5b42c7e5e",
            "external_blobs": {
                "form.xml": {
                    "content_length": 34282,
                    "content_type": "text/xml",
                    "digest": "md5-EhgFC+ZQGc7pGTu7CwMRwA==",
                    "doc_type": "BlobMeta",
                    "id": "form.xml.11764c68ee5e41b69b748fc76d69e309"
                }
            }
        }
        # this line previously failed hard when called
        FakeCouchDocument.wrap(doc)


class TestBlobMixinWithS3Backend(TestBlobMixin):

    @classmethod
    def setUpClass(cls):
        super(TestBlobMixinWithS3Backend, cls).setUpClass()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.db = TemporaryS3BlobDB(config)

    class TestBlob(object):

        def __init__(self, db, key):
            self.db = db
            self.key = self.path = key

        @property
        def s3_bucket(self):
            return self.db.db.Bucket(self.db.s3_bucket_name)

        def exists(self):
            with maybe_not_found():
                self.s3_bucket.Object(self.key).load()
                return True
            return False

        def open(self):
            obj = self.s3_bucket.Object(self.key).get()
            return ClosingContextProxy(obj["Body"])

        def listdir(self):
            summaries = self.s3_bucket.objects.filter(Prefix="/")
            with maybe_not_found():
                return [o.key for o in summaries]
            return []


class TestBlobMixinWithMigratingDbBeforeCopyToNew(TestBlobMixinWithS3Backend):

    @classmethod
    def setUpClass(cls):
        super(TestBlobMixinWithMigratingDbBeforeCopyToNew, cls).setUpClass()
        cls.db = PutInOldBlobDB(cls.db, TemporaryFilesystemBlobDB())

    class TestBlob(TestBlobMixinWithS3Backend.TestBlob):

        def __init__(self, db, key):
            self.db = db.new_db
            self.key = self.path = key
            self.fspath = db.old_db.get_path(key=key)

        def exists(self):
            super_ = super(TestBlobMixinWithMigratingDbBeforeCopyToNew.TestBlob, self)
            return super_.exists() or os.path.exists(self.fspath)

        def open(self):
            super_ = super(TestBlobMixinWithMigratingDbBeforeCopyToNew.TestBlob, self)
            if super_.exists():
                return super_.open()
            return open(self.fspath, 'rb')

        def listdir(self):
            path = self.fspath
            if "/" in self.key:
                assert path.endswith("/" + self.key), (path, self.key)
                path = path[:-len(self.key) - 1]
            else:
                path = os.path.dirname(path)
            super_ = super(TestBlobMixinWithMigratingDbBeforeCopyToNew.TestBlob, self)
            return super_.listdir() or os.listdir(path)


class TestBlobMixinWithMigratingDbAfterCopyToNew(TestBlobMixinWithMigratingDbBeforeCopyToNew):

    @classmethod
    def setUpClass(cls):
        # intentional call to super super setUpClass
        super(TestBlobMixinWithMigratingDbBeforeCopyToNew, cls).setUpClass()
        cls.db = PutInOldCopyToNewBlobDB(cls.db, TemporaryFilesystemBlobDB())


class TestBlobHelper(BaseTestCase):

    def setUp(self):
        self.couch = FakeCouchDatabase()

    def make_doc(self, type_=mod.BlobHelper, doc=None):
        if doc is None:
            doc = {}
        if "_id" not in doc:
            doc["_id"] = uuid.uuid4().hex
        if "domain" not in doc:
            doc["domain"] = "test"
        if "doc_type" not in doc:
            doc["doc_type"] = "FakeDoc"
        if doc.get("_attachments"):
            for name, attach in six.iteritems(doc["_attachments"]):
                self.couch.put_attachment(doc, name=name, **attach)
        external = doc.get("external_blobs", {})
        if external and all("content" in b for b in external.values()):
            doc["external_blobs"] = {}
        obj = type_(doc, self.couch, CODES.multimedia)
        if external:
            save_log = list(self.couch.save_log)
            for name, attach in list(six.iteritems(external)):
                obj.put_attachment(name=name, **attach)
            self.couch.save_log = save_log
        return obj

    def test_put_attachment_for_doc_with_bad_path_id(self):
        obj = self.make_doc(doc={
            "_id": "uuid:some-random-value",
            "external_blobs": {},
        })
        name = "test.0"
        data = "\u4500 content"
        obj.put_attachment(data, name)
        self.assertEqual(obj.fetch_attachment(name).decode('utf-8'), data)

    def test_put_and_fetch_attachment_from_couch(self):
        obj = self.make_doc(doc={"_attachments": {}})
        content = b"test couch"
        self.assertFalse(self.couch.data)
        obj.put_attachment(content, "file.txt", content_type="text/plain")
        self.assertEqual(obj.fetch_attachment("file.txt"), content)
        self.assertTrue(self.couch.data)
        self.assertFalse(self.couch.save_log)

    def test_put_attachment_error_on_ambiguous_backend(self):
        obj = self.make_doc()
        with self.assertRaises(mod.AmbiguousBlobStorageError):
            obj.put_attachment("test", "file.txt", content_type="text/plain")

    def test_fetch_attachment_do_not_hit_couch_when_not_migrating(self):
        def fetch_fail(*args, **kw):
            raise Exception("fail!")
        couch = FakeCouchDatabase()
        couch.fetch_attachment = fetch_fail
        obj = mod.BlobHelper({
            "doc_type": "FakeDoc",
            "domain": "test",
            "_id": "fetch-fail",
            "external_blobs": {"not-found.txt": {"id": "hahaha"}},
        }, couch, CODES.multimedia)
        self.assertFalse(obj._migrating_blobs_from_couch)
        with self.assertRaisesMessage(mod.ResourceNotFound, '{} attachment'.format(obj._id)):
            obj.fetch_attachment("not-found.txt")

    def test_fetch_attachment_not_found_while_migrating(self):
        obj = mod.BlobHelper({
            "doc_type": "FakeDoc",
            "domain": "test",
            "_id": "fetch-fail",
            "_attachments": {"migrating...": {}},
            "external_blobs": {"not-found.txt": {"id": "nope"}},
        }, self.couch, CODES.multimedia)
        self.assertTrue(obj._migrating_blobs_from_couch)
        with self.assertRaisesMessage(mod.ResourceNotFound, '{} attachment'.format(obj._id)):
            obj.fetch_attachment("not-found.txt")

    def test_put_and_fetch_attachment_from_blob_db(self):
        obj = self.make_doc(doc={"external_blobs": {}})
        content = b"test blob"
        self.assertFalse(self.couch.data)
        obj.put_attachment(content, "file.txt", content_type="text/plain")
        self.assertEqual(obj.fetch_attachment("file.txt"), content)
        self.assertFalse(self.couch.data)
        self.assertEqual(self.couch.save_log, [{
            "doc_type": "FakeDoc",
            "domain": "test",
            "_id": obj._id,
            "external_blobs": {
                "file.txt": {
                    "key": obj.blobs["file.txt"].key,
                    "blobmeta_id": obj.blobs["file.txt"].blobmeta_id,
                    "content_type": "text/plain",
                    "content_length": 9,
                    "doc_type": "BlobMetaRef",
                },
            },
        }])

    def test_fetch_attachment_from_multi_backend_doc(self):
        obj = self.make_doc(doc={
            "_attachments": {
                "couch.txt": {
                    "content_type": "text/plain",
                    "content": "couch",
                },
            },
            "external_blobs": {
                "blob.txt": {
                    "content_type": "text/plain",
                    "content": "blob",
                }
            },
        })
        self.assertTrue(obj._migrating_blobs_from_couch)
        self.assertEqual(obj.fetch_attachment("couch.txt"), "couch")
        self.assertEqual(obj.fetch_attachment("blob.txt"), b"blob")
        self.assertFalse(self.couch.save_log)

    def test_atomic_blobs_with_couch_attachments(self):
        obj = self.make_doc(doc={"_attachments": {}})
        self.assertFalse(self.couch.data)
        self.assertFalse(obj._migrating_blobs_from_couch)
        with obj.atomic_blobs():
            # save before put
            self.assertEqual(self.couch.save_log, [{
                "doc_type": "FakeDoc",
                "domain": "test",
                "_id": obj._id,
                "_attachments": {},
            }])
            obj.put_attachment("test", "file.txt", content_type="text/plain")
        self.assertEqual(len(self.couch.save_log), 1)  # no new save
        self.assertEqual(obj.fetch_attachment("file.txt"), "test")
        self.assertTrue(self.couch.data)

    def test_atomic_blobs_with_external_blobs(self):
        obj = self.make_doc(doc={"_attachments": {}, "external_blobs": {}})
        self.assertFalse(self.couch.data)
        self.assertFalse(obj._migrating_blobs_from_couch)
        with obj.atomic_blobs():
            # no save before put
            self.assertEqual(self.couch.save_log, [])
            obj.put_attachment("test", "file.txt", content_type="text/plain")
        self.assertEqual(self.couch.save_log, [{
            "doc_type": "FakeDoc",
            "domain": "test",
            "_id": obj._id,
            "_attachments": {},
            "external_blobs": {
                "file.txt": {
                    "key": obj.blobs["file.txt"].key,
                    "blobmeta_id": obj.blobs["file.txt"].blobmeta_id,
                    "content_type": "text/plain",
                    "content_length": 4,
                    "doc_type": "BlobMetaRef",
                },
            },
        }])
        self.assertEqual(obj.fetch_attachment("file.txt"), b"test")
        self.assertFalse(self.couch.data)

    def test_atomic_blobs_with_migrating_couch_attachments(self):
        obj = self.make_doc(doc={
            "_attachments": {
                "doc.txt": {
                    "content_type": "text/plain",
                    "content": "doc",
                },
            },
            "external_blobs": {},
        })
        self.assertEqual(len(self.couch.data), 1)
        self.assertTrue(obj._migrating_blobs_from_couch)
        with obj.atomic_blobs():
            # no save before put
            self.assertEqual(self.couch.save_log, [])
            # fetch from couch
            content = obj.fetch_attachment("doc.txt")
            # put in blob db
            obj.put_attachment(content, "doc.txt", content_type="text/plain")
        # couch attachment removed
        self.assertNotIn("doc.txt", obj.doc["_attachments"])
        self.assertEqual(self.couch.meta, {})
        # fetch from blob db
        self.assertEqual(obj.fetch_attachment("doc.txt"), b"doc")
        self.assertEqual(self.couch.save_log, [{
            "doc_type": "FakeDoc",
            "_id": obj._id,
            "domain": "test",
            "_attachments": {},
            "external_blobs": {
                "doc.txt": {
                    "key": obj.blobs["doc.txt"].key,
                    "blobmeta_id": obj.blobs["doc.txt"].blobmeta_id,
                    "content_type": "text/plain",
                    "content_length": 3,
                    "doc_type": "BlobMetaRef",
                },
            },
        }])

    def test_atomic_blobs_maintains_attachments_on_error(self):
        obj = self.make_doc(doc={
            "_attachments": {
                "doc.txt": {
                    "content_type": "text/plain",
                    "content": "doc",
                },
            },
            "external_blobs": {},
        })
        self.assertEqual(len(self.couch.data), 1)
        self.assertTrue(obj._migrating_blobs_from_couch)
        with self.assertRaises(Exception), obj.atomic_blobs():
            # no save before put
            self.assertEqual(self.couch.save_log, [])
            # fetch from couch
            content = obj.fetch_attachment("doc.txt")
            # put in blob db
            obj.put_attachment(content, "doc.txt", content_type="text/plain")
            # should restore state to how it was before atomic_blobs()
            raise Exception("fail!")
        # couch attachment preserved
        self.assertEqual(obj.external_blobs, obj.doc["external_blobs"])
        self.assertEqual(obj._attachments, obj.doc["_attachments"])
        self.assertIn("doc.txt", obj.doc["_attachments"])
        self.assertFalse(obj.doc["external_blobs"])
        self.assertTrue(self.couch.meta)


class TestBulkAtomicBlobs(BaseTestCase):

    def test_bulk_atomic_blobs(self):
        docs = [self.obj]
        self.assertNotIn("name", self.obj.blobs)
        with mod.bulk_atomic_blobs(docs):
            self.obj.put_attachment("data", "name")
            self.assertIn("name", self.obj.blobs)
        self.assertFalse(self.obj.saved)
        self.assertEqual(self.obj.fetch_attachment("name"), b"data")

    def test_bulk_atomic_blobs_with_deferred_blobs(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        self.assertNotIn("name", obj.blobs)
        obj.deferred_put_attachment("data", "name")
        docs = [obj]
        with mod.bulk_atomic_blobs(docs):
            obj.put_attachment("data", "name")
            self.assertIn("name", obj.external_blobs)
            key = obj.blobs["name"].key
            self.assertTrue(key)
        self.assertFalse(obj.saved)
        with self.get_blob(key).open() as fh:
            self.assertEqual(fh.read(), b"data")

    def test_bulk_atomic_blobs_with_deferred_deleted_blobs(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        self.assertNotIn("will_delete", obj.blobs)
        obj.put_attachment("data", "will_delete")
        obj.deferred_delete_attachment("will_delete")
        docs = [obj]
        meta = obj.external_blobs["will_delete"]
        with mod.bulk_atomic_blobs(docs):
            self.assertNotIn("will_delete", obj.external_blobs)
            self.assertTrue(self.db.exists(key=meta.key))
        self.assertFalse(obj._deferred_blobs)
        self.assertFalse(self.db.exists(key=meta.key))
        self.assertNotIn("will_delete", obj.external_blobs)

    def test_bulk_atomic_blobs_with_non_blob_docs(self):
        noblobs = self.make_doc(BaseFakeDocument)
        self.assertFalse(hasattr(noblobs, "blobs"))
        docs = [noblobs]
        with mod.bulk_atomic_blobs(docs):
            pass
        self.assertFalse(noblobs.saved)

    def test_bulk_atomic_blobs_with_mixed_docs(self):
        noblobs = self.make_doc(BaseFakeDocument)
        deferred = self.make_doc(DeferredPutBlobDocument)
        deferred.deferred_put_attachment("deferred", "att")
        self.assertFalse(hasattr(noblobs, "blobs"))
        docs = [self.obj, noblobs, deferred]
        self.assertNotIn("name", self.obj.blobs)
        with mod.bulk_atomic_blobs(docs):
            self.obj.put_attachment("data", "name")
            self.assertIn("name", self.obj.blobs)
            self.assertIn("att", deferred.external_blobs)
        self.assertFalse(any(d.saved for d in docs))
        self.assertEqual(self.obj.fetch_attachment("name"), b"data")
        key = deferred.blobs["att"].key
        with self.get_blob(key).open() as fh:
            self.assertEqual(fh.read(), b"deferred")


_abc_digest = mod.sha1(b"abc").hexdigest()


@generate_cases([
    ("abc-def", "abc-def"),
    ("{abc-def}", "{abc-def}"),
    ("uuid:def", "sha1-d7ceb3d1678b9986f89e88780094a571a226c8b5"),
    ("sha1-def", "sha1-def"),
    ("sha1-" + _abc_digest + "0", "sha1-" + _abc_digest + "0"),
    ("sha1-" + _abc_digest, ValueError),
])
def test_safe_id(self, value, result):
    if isinstance(result, type):
        with self.assertRaises(result):
            mod.safe_id(value)
    else:
        self.assertEqual(mod.safe_id(value), result)


class FakeCouchDatabase(object):

    def __init__(self, name="couch"):
        self.dbname = name
        self.meta = {}
        self.data = {}
        self.save_log = []

    def put_attachment(self, doc, content, name, **meta):
        key = (doc["_id"], name)
        self.meta[key] = meta
        self.data[key] = content or ""
        if doc.get("_attachments") is None:
            doc["_attachments"] = {}
        doc["_attachments"][name] = meta

    def fetch_attachment(self, doc_id, name, stream=False):
        assert not stream, 'not implemented'
        return self.data[(doc_id, name)]

    def save_doc(self, doc):
        attachments = doc.get("_attachments") or {}
        for key in list(self.data):
            if key[0] == doc["_id"] and key[1] not in attachments:
                # remove deleted attachment
                del self.data[key]
                del self.meta[key]
        self.save_log.append(deepcopy(doc))


class PutInOldBlobDB(TemporaryMigratingBlobDB):

    def put(self, *args, **kw):
        return self.old_db.put(*args, **kw)


class PutInOldCopyToNewBlobDB(TemporaryMigratingBlobDB):

    def put(self, content, *args, **kw):
        meta = self.old_db.put(content, *args, **kw)
        content.seek(0)
        self.copy_blob(content, key=meta.key)
        return meta


class BaseFakeDocument(Document):

    class Meta(object):
        app_label = "couch"

    saved = False

    def save(self):
        # couchdbkit does this (essentially)
        # it creates new BlobMetaRef instances in self.external_blobs
        self._doc.update(deepcopy(self._doc))
        self.saved = True

    @classmethod
    def get_db(cls):
        class fake_db(object):
            dbname = "commcarehq_test"

            class server(object):

                @staticmethod
                def next_uuid():
                    return uuid.uuid4().hex
        return fake_db


class FakeCouchDocument(mod.BlobMixin, BaseFakeDocument):

    class Meta(object):
        app_label = "couch"

    doc_type = "FakeCouchDocument"
    domain = "test"
    _blobdb_type_code = CODES.multimedia


class DeferredPutBlobDocument(mod.DeferredBlobMixin, BaseFakeDocument):

    class Meta(object):
        app_label = "couch"

    domain = "test"
    _blobdb_type_code = CODES.multimedia


class FailingSaveCouchDocument(FakeCouchDocument):

    allow_saves = 1

    def save(self):
        if self.allow_saves:
            super(FailingSaveCouchDocument, self).save()
            self.allow_saves -= 1
        else:
            raise BlowUp("save failed")


class AttachmentFallback(object):

    def __init__(self, *args, **kw):
        super(AttachmentFallback, self).__init__(*args, **kw)
        self._attachments = {}

    def put_attachment(self, *args, **kw):
        raise NotImplementedError

    def fetch_attachment(self, name, stream=False):
        if name in self._attachments:
            return self._attachments[name]["content"]
        raise mod.ResourceNotFound

    def delete_attachment(self, name):
        value = self._attachments.pop(name, None)
        return value is not None


class FallbackToCouchDocument(mod.BlobMixin, AttachmentFallback, Document):

    class Meta(object):
        app_label = "couch"

    doc_type = "FallbackToCouchDocument"
    domain = "test"
    _migrating_blobs_from_couch = True
    _blobdb_type_code = CODES.multimedia

    @classmethod
    def get_db(cls):
        class fake_db(object):
            dbname = "commcarehq_test"

            @staticmethod
            def save_doc(doc, **params):
                pass
        return fake_db


class BlowUp(Exception):
    pass
