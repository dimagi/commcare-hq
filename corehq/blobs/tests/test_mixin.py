from __future__ import unicode_literals
import os
import uuid
from base64 import b64encode
from copy import deepcopy
from hashlib import md5
from os.path import join
from StringIO import StringIO

from django.conf import settings
from django.test import SimpleTestCase

import corehq.blobs.mixin as mod
from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.s3db import ClosingContextProxy, maybe_not_found
from corehq.blobs.tests.util import (TemporaryFilesystemBlobDB,
    TemporaryMigratingBlobDB, TemporaryS3BlobDB)
from corehq.util.test_utils import generate_cases, trap_extra_setup
from dimagi.ext.couchdbkit import Document


class BaseTestCase(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def make_doc(self, type_=None, id=None):
        if type_ is None:
            type_ = FakeCouchDocument
        if id is None:
            id = uuid.uuid4().hex
        return type_({"_id": id})

    def setUp(self):
        self.obj = self.make_doc()

    def get_blob(self, name=None, bucket=None):
        return self.TestBlob(self.db, name, bucket)

    class TestBlob(object):

        def __init__(self, db, name, bucket):
            self.db = db
            self.path = db.get_path(name, bucket)

        def exists(self):
            return os.path.exists(self.path)

        def open(self):
            return open(self.path)

        def listdir(self):
            return os.listdir(self.path)


class TestBlobMixin(BaseTestCase):

    def test_put_attachment_without_name(self):
        with self.assertRaises(mod.InvalidAttachment):
            self.obj.put_attachment("content")

    def test_put_attachment_for_doc_with_bad_path_id(self):
        obj = self.make_doc(id="uuid:some-random-value")
        name = "test.0"
        data = "\u4500 content"
        obj.put_attachment(data, name)
        self.assertEqual(obj.fetch_attachment(name), data)

    def test_put_attachment_unicode(self):
        name = "test.1"
        data = "\u4500 content"
        self.obj.put_attachment(data, name)
        self.assertEqual(self.obj.fetch_attachment(name), data)

    def test_put_attachment_bytes(self):
        name = "test.1"
        data = b"\xe4\x94 content"  # cannot be decoded as UTF-8
        self.obj.put_attachment(data, name)
        self.assertEqual(self.obj.fetch_attachment(name), data)

    def test_put_attachment_with_named_content(self):
        content = StringIO(b"content")
        content.name = "test.1"
        self.obj.put_attachment(content)
        self.assertEqual(self.obj.fetch_attachment(content.name), "content")
        self.assertTrue(self.obj.saved)

    def test_fetch_attachment_with_unicode(self):
        name = "test.1"
        content = "\u4500 is not ascii"
        self.obj.put_attachment(content, name)
        self.assertEqual(self.obj.fetch_attachment(name), content)

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
        content = StringIO(b"content")
        self.obj.put_attachment(content, name, content_type="text/plain")
        self.assertEqual(self.obj.blobs[name].content_type, "text/plain")
        self.assertEqual(self.obj.blobs[name].content_length, 7)

    def test_deferred_put_attachment(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        content = StringIO(b"content")
        obj.deferred_put_attachment(content, name, content_type="text/plain")
        self.assertEqual(obj.blobs[name].id, None)
        self.assertEqual(obj.blobs[name].content_type, "text/plain")
        self.assertEqual(obj.blobs[name].content_length, 7)
        self.assertFalse(obj.saved)

    def test_put_attachment_overwrites_unsaved_blob(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        name = "test.1"
        obj.deferred_put_attachment(b"<xml />", name, content_type="text/xml")
        obj.put_attachment(b"new", name, content_type="text/plain")
        self.assertTrue(obj.blobs[name].id is not None)
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

    def test_persistent_blobs(self):
        content = b"<xml />"
        couch_digest = "md5-" + b64encode(md5(content).digest())
        obj = self.make_doc(DeferredPutBlobDocument)
        obj.migrating_blobs_from_couch = True
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
        content = StringIO(b"content")
        obj.deferred_put_attachment(content, name, content_type="text/plain")
        obj.save()
        self.assertTrue(obj.saved)
        self.assertTrue(obj.blobs[name].id is not None)
        self.assertEqual(obj.blobs[name].content_type, "text/plain")
        self.assertEqual(obj.blobs[name].content_length, 7)

    def test_blob_directory(self):
        name = "test.1"
        content = StringIO(b"test_blob_directory content")
        self.obj.put_attachment(content, name)
        bucket = join("commcarehq_test", self.obj._id)
        blob = self.get_blob(self.obj.blobs[name].id, bucket)
        with blob.open() as fh:
            self.assertEqual(fh.read(), b"test_blob_directory content")

    def test_put_attachment_deletes_replaced_blob(self):
        name = "test.\u4500"
        bucket = self.obj._blobdb_bucket()
        self.obj.put_attachment("content 1", name)
        blob1 = self.get_blob(self.obj.blobs[name].id, bucket)
        self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].id, bucket)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected file: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), "content 2")

    def test_put_attachment_failed_save_does_not_delete_replaced_blob(self):
        name = "test.\u4500"
        doc = self.make_doc(FailingSaveCouchDocument)
        bucket = doc._blobdb_bucket()
        doc.put_attachment("content 1", name)
        old_blob = doc.blobs[name]
        with self.assertRaises(BlowUp):
            doc.put_attachment("content 2", name)
        blob = self.get_blob(old_blob.id, bucket)
        doc.blobs[name] = old_blob  # simulate get from couch
        self.assertTrue(blob.exists(), "not found: " + blob.path)
        self.assertEqual(doc.fetch_attachment(name), "content 1")

    def test_put_attachment_deletes_couch_attachment(self):
        name = "test"
        content = StringIO(b"content")
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments = {name: {"length": 25}}
        doc.put_attachment(content, name)
        self.assertEqual(doc.fetch_attachment(name), "content")
        self.assertNotIn(name, doc._attachments)

    def test_fallback_on_fetch_fail(self):
        name = "test.1"
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments[name] = {"content": b"couch content"}
        self.assertEqual(doc.fetch_attachment(name), b"couch content")

    def test_fallback_on_delete_fail(self):
        name = "test.1"
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments[name] = {"content": b"couch content"}
        self.assertTrue(doc.delete_attachment(name), "couch attachment not deleted")
        self.assertNotIn(name, doc._attachments)

    def test_blobs_property(self):
        couch_digest = "md5-" + b64encode(md5(b"content").digest())
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments["att"] = {
            "content": b"couch content",
            "content_type": None,
            "digest": couch_digest,
            "length": 13,
        }
        doc.put_attachment("content", "blob", content_type="text/plain")
        self.assertIn("att", doc.blobs)
        self.assertIn("blob", doc.blobs)
        self.assertEqual(doc.blobs["att"].content_length, 13)
        self.assertEqual(doc.blobs["att"].digest, couch_digest)
        self.assertEqual(doc.blobs["blob"].content_length, 7)
        self.assertEqual(doc.blobs["blob"].digest,
                         "md5-" + b64encode(md5(b"content").digest()))

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
        self.assertEqual(self.obj.fetch_attachment(name), "content")
        self.assertIn(name, self.obj.blobs)

    def test_atomic_blobs_success_and_new_id(self):
        name = "test.1"
        obj = FakeCouchDocument()
        obj._id = None
        with obj.atomic_blobs():
            obj.put_attachment("content", name)
        self.assertTrue(obj.saved)
        self.assertTrue(obj._id is not None)
        self.assertEqual(obj.fetch_attachment(name), "content")
        self.assertIn(name, obj.blobs)

    def test_atomic_blobs_deletes_replaced_blob(self):
        name = "test.\u4500"
        bucket = self.obj._blobdb_bucket()
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
        blob1 = self.get_blob(self.obj.blobs[name].id, bucket)
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].id, bucket)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected blob: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), "content 2")

    def test_atomic_blobs_deletes_replaced_blob_in_same_context(self):
        name = "test.\u4500"
        bucket = self.obj._blobdb_bucket()
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
            blob1 = self.get_blob(self.obj.blobs[name].id, bucket)
            self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].id, bucket)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected blob: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), "content 2")

    def test_atomic_blobs_deletes_replaced_blob_in_nested_context(self):
        name = "test.\u4500"
        bucket = self.obj._blobdb_bucket()
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
            blob1 = self.get_blob(self.obj.blobs[name].id, bucket)
            with self.obj.atomic_blobs():
                self.obj.put_attachment("content 2", name)
        blob2 = self.get_blob(self.obj.blobs[name].id, bucket)
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob1.exists(), "found unexpected blob: " + blob1.path)
        self.assertEqual(self.obj.fetch_attachment(name), "content 2")

    def test_atomic_blobs_preserves_blob_replaced_in_failed_nested_context(self):
        name = "test.\u4500"
        bucket = self.obj._blobdb_bucket()
        with self.obj.atomic_blobs():
            self.obj.put_attachment("content 1", name)
            blob1 = self.get_blob(self.obj.blobs[name].id, bucket)
            with self.assertRaises(BlowUp):
                with self.obj.atomic_blobs():
                    self.obj.put_attachment("content 2", name)
                    blob2 = self.get_blob(self.obj.blobs[name].id, bucket)
                    raise BlowUp("fail")
        self.assertNotEqual(blob1.path, blob2.path)
        self.assertFalse(blob2.exists(), "found unexpected blob: " + blob2.path)
        self.assertEqual(self.obj.fetch_attachment(name), "content 1")

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
        with self.assertRaises(BlowUp):
            with self.obj.atomic_blobs():
                self.obj.put_attachment("new content", name)
                raise BlowUp("while saving atomic blobs")
        self.assertEqual(self.obj.blobs[name].content_length, 7)
        self.assertEqual(self.obj.fetch_attachment(name), "content")
        # verify cleanup
        blob = self.get_blob(bucket=self.obj._blobdb_bucket())
        self.assertEqual(len(blob.listdir()), len(self.obj.blobs))

    def test_atomic_blobs_fail_restores_couch_attachments(self):
        couch_digest = "md5-" + b64encode(md5(b"content").digest())
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments["att"] = {
            "content": b"couch content",
            "content_type": None,
            "digest": couch_digest,
            "length": 13,
        }
        with self.assertRaises(BlowUp):
            with doc.atomic_blobs():
                doc.put_attachment("new content", "att")
                raise BlowUp("while saving atomic blobs")
        self.assertEqual(doc.blobs["att"].content_length, 13)
        self.assertEqual(doc.fetch_attachment("att"), "couch content")
        # verify cleanup
        blob = self.get_blob(bucket=doc._blobdb_bucket())
        self.assertEqual(len(blob.listdir()), 0)

    def test_atomic_blobs_fail_restores_deleted_blob(self):
        name = "delete-fail"
        self.obj.put_attachment("content", name)
        with self.assertRaises(BlowUp):
            with self.obj.atomic_blobs():
                self.obj.delete_attachment(name)
                raise BlowUp("while deleting blob")
        self.assertEqual(self.obj.blobs[name].content_length, 7)
        self.assertEqual(self.obj.fetch_attachment(name), "content")
        # verify cleanup
        blob = self.get_blob(bucket=self.obj._blobdb_bucket())
        self.assertEqual(len(blob.listdir()), len(self.obj.blobs))

    def test_atomic_blobs_fail_restores_deleted_couch_attachment(self):
        couch_digest = "md5-" + b64encode(md5(b"content").digest())
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments["att"] = {
            "content": b"couch content",
            "content_type": None,
            "digest": couch_digest,
            "length": 13,
        }
        with self.assertRaises(BlowUp):
            with doc.atomic_blobs():
                doc.delete_attachment("att")
                raise BlowUp("while deleting couch attachment")
        self.assertEqual(doc.blobs["att"].content_length, 13)
        self.assertEqual(doc.fetch_attachment("att"), "couch content")
        # verify cleanup
        blob = self.get_blob(bucket=doc._blobdb_bucket())
        self.assertTrue(not blob.exists() or len(blob.listdir()) == 0)

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
        self.assertEqual(self.obj.fetch_attachment("file"), "file content")

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
        self.assertEqual(self.obj.fetch_attachment("file"), "file content")


class TestBlobMixinWithS3Backend(TestBlobMixin):

    @classmethod
    def setUpClass(cls):
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.db = TemporaryS3BlobDB(config)

    class TestBlob(object):

        def __init__(self, db, name, bucket):
            self.db = db
            self.path = db.get_path(name, bucket)

        @property
        def s3_bucket(self):
            return self.db.db.Bucket(self.db.s3_bucket_name)

        def exists(self):
            with maybe_not_found():
                self.s3_bucket.Object(self.path).load()
                return True
            return False

        def open(self):
            obj = self.s3_bucket.Object(self.path).get()
            return ClosingContextProxy(obj["Body"])

        def listdir(self):
            summaries = self.s3_bucket.objects.filter(Prefix=self.path + "/")
            with maybe_not_found():
                return [o.key for o in summaries]
            return []


class TestBlobMixinWithMigratingDbBeforeCopyToNew(TestBlobMixinWithS3Backend):

    @classmethod
    def setUpClass(cls):
        super(TestBlobMixinWithMigratingDbBeforeCopyToNew, cls).setUpClass()
        cls.db = PutInOldBlobDB(cls.db, TemporaryFilesystemBlobDB())

    class TestBlob(TestBlobMixinWithS3Backend.TestBlob):

        def __init__(self, db, name, bucket):
            self.db = db.new_db
            self.path = db.new_db.get_path(name, bucket)
            self.fspath = db.old_db.get_path(name, bucket)

        def exists(self):
            super_ = super(TestBlobMixinWithMigratingDbBeforeCopyToNew.TestBlob, self)
            return super_.exists() or os.path.exists(self.fspath)

        def open(self):
            super_ = super(TestBlobMixinWithMigratingDbBeforeCopyToNew.TestBlob, self)
            if super_.exists():
                return super_.open()
            return open(self.fspath)

        def listdir(self):
            super_ = super(TestBlobMixinWithMigratingDbBeforeCopyToNew.TestBlob, self)
            return super_.listdir() or os.listdir(self.fspath)


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
        if doc.get("_attachments"):
            for name, attach in doc["_attachments"].iteritems():
                self.couch.put_attachment(doc, name=name, **attach)
        obj = type_(doc, self.couch)
        if "external_blobs" in doc:
            save_log = list(self.couch.save_log)
            for name, attach in list(doc["external_blobs"].iteritems()):
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
        self.assertEqual(obj.fetch_attachment(name), data)

    def test_put_and_fetch_attachment_from_couch(self):
        obj = self.make_doc(doc={"_attachments": {}})
        content = "test couch"
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
            "_id": "fetch-fail",
            "external_blobs": {"not-found.txt": {"id": "hahaha"}},
        }, couch)
        self.assertFalse(obj.migrating_blobs_from_couch)
        with self.assertRaisesMessage(mod.ResourceNotFound, '{} attachment'.format(obj._id)):
            obj.fetch_attachment("not-found.txt")

    def test_fetch_attachment_not_found_while_migrating(self):
        obj = mod.BlobHelper({
            "_id": "fetch-fail",
            "_attachments": {"migrating...": {}},
            "external_blobs": {"not-found.txt": {"id": "nope"}},
        }, self.couch)
        self.assertTrue(obj.migrating_blobs_from_couch)
        with self.assertRaisesMessage(mod.ResourceNotFound, '{} attachment'.format(obj._id)):
            obj.fetch_attachment("not-found.txt")

    def test_put_and_fetch_attachment_from_blob_db(self):
        obj = self.make_doc(doc={"external_blobs": {}})
        content = "test blob"
        self.assertFalse(self.couch.data)
        obj.put_attachment(content, "file.txt", content_type="text/plain")
        self.assertEqual(obj.fetch_attachment("file.txt"), content)
        self.assertFalse(self.couch.data)
        self.assertEqual(self.couch.save_log, [{
            "_id": obj._id,
            "external_blobs": {
                "file.txt": {
                    "id": obj.blobs["file.txt"].id,
                    "content_type": "text/plain",
                    "content_length": 9,
                    "digest": "md5-PKF0bQ5Vl99sgbsjAnyNQA==",
                    "doc_type": "BlobMeta",
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
        self.assertTrue(obj.migrating_blobs_from_couch)
        self.assertEqual(obj.fetch_attachment("couch.txt"), "couch")
        self.assertEqual(obj.fetch_attachment("blob.txt"), "blob")
        self.assertFalse(self.couch.save_log)

    def test_atomic_blobs_with_couch_attachments(self):
        obj = self.make_doc(doc={"_attachments": {}})
        self.assertFalse(self.couch.data)
        self.assertFalse(obj.migrating_blobs_from_couch)
        with obj.atomic_blobs():
            # save before put
            self.assertEqual(self.couch.save_log, [{
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
        self.assertFalse(obj.migrating_blobs_from_couch)
        with obj.atomic_blobs():
            # no save before put
            self.assertEqual(self.couch.save_log, [])
            obj.put_attachment("test", "file.txt", content_type="text/plain")
        self.assertEqual(self.couch.save_log, [{
            "_id": obj._id,
            "_attachments": {},
            "external_blobs": {
                "file.txt": {
                    "id": obj.blobs["file.txt"].id,
                    "content_type": "text/plain",
                    "content_length": 4,
                    "digest": "md5-CY9rzUYh03PK3k6DJie09g==",
                    "doc_type": "BlobMeta",
                },
            },
        }])
        self.assertEqual(obj.fetch_attachment("file.txt"), "test")
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
        self.assertTrue(obj.migrating_blobs_from_couch)
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
        self.assertEqual(obj.fetch_attachment("doc.txt"), "doc")
        self.assertEqual(self.couch.save_log, [{
            "_id": obj._id,
            "_attachments": {},
            "external_blobs": {
                "doc.txt": {
                    "id": obj.blobs["doc.txt"].id,
                    "content_type": "text/plain",
                    "content_length": 3,
                    "digest": "md5-mgm039qC4+Zl4xCS0cPsjQ==",
                    "doc_type": "BlobMeta",
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
        self.assertTrue(obj.migrating_blobs_from_couch)
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
        self.assertEqual(self.obj.fetch_attachment("name"), "data")

    def test_bulk_atomic_blobs_with_deferred_blobs(self):
        obj = self.make_doc(DeferredPutBlobDocument)
        self.assertNotIn("name", obj.blobs)
        obj.deferred_put_attachment("data", "name")
        docs = [obj]
        with mod.bulk_atomic_blobs(docs):
            obj.put_attachment("data", "name")
            self.assertIn("name", obj.external_blobs)
            ident = obj.blobs["name"].id
            self.assertTrue(ident)
        self.assertFalse(obj.saved)
        with self.get_blob(ident, obj._blobdb_bucket()).open() as fh:
            self.assertEqual(fh.read(), "data")

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
        self.assertEqual(self.obj.fetch_attachment("name"), "data")
        ident = deferred.blobs["att"].id
        with self.get_blob(ident, deferred._blobdb_bucket()).open() as fh:
            self.assertEqual(fh.read(), "deferred")


_abc_digest = mod.sha1("abc").hexdigest()


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

    def put(self, content, identifier=None, bucket=DEFAULT_BUCKET):
        info = self.old_db.put(content, identifier, bucket=bucket)
        content.seek(0)
        self.copy_blob(content, info, bucket)
        return info


class BaseFakeDocument(Document):

    class Meta:
        app_label = "couch"

    saved = False

    def save(self):
        # couchdbkit does this (essentially)
        # it creates new BlobMeta instances in self.external_blobs
        self._doc.update(deepcopy(self._doc))
        self.saved = True

    @classmethod
    def get_db(cls):
        class fake_db:
            dbname = "commcarehq_test"

            class server:

                @staticmethod
                def next_uuid():
                    return uuid.uuid4().hex
        return fake_db


class FakeCouchDocument(mod.BlobMixin, BaseFakeDocument):

    class Meta:
        app_label = "couch"

    doc_type = "FakeCouchDocument"


class DeferredPutBlobDocument(mod.DeferredBlobMixin, BaseFakeDocument):

    class Meta:
        app_label = "couch"


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

    class Meta:
        app_label = "couch"

    doc_type = "FallbackToCouchDocument"
    migrating_blobs_from_couch = True

    @classmethod
    def get_db(cls):
        class fake_db:
            dbname = "commcarehq_test"

            @staticmethod
            def save_doc(doc, **params):
                pass
        return fake_db


class BlowUp(Exception):
    pass
