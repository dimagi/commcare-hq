from __future__ import unicode_literals
import os
import uuid
from base64 import b64encode
from hashlib import md5
from os.path import join
from unittest import TestCase
from StringIO import StringIO

from django.conf import settings

import corehq.blobs.mixin as mod
from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.s3db import ClosingContextProxy, maybe_not_found
from corehq.blobs.tests.util import (TemporaryFilesystemBlobDB,
    TemporaryMigratingBlobDB, TemporaryS3BlobDB)
from corehq.util.test_utils import trap_extra_setup
from dimagi.ext.couchdbkit import Document


class BaseTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def make_doc(self, type_):
        return type_({"_id": uuid.uuid4().hex})

    def setUp(self):
        self.obj = self.make_doc(FakeCouchDocument)


class TestBlobMixin(BaseTestCase):

    def test_put_attachment_without_name(self):
        with self.assertRaises(mod.InvalidAttachment):
            self.obj.put_attachment("content")

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


class PutInOldBlobDB(TemporaryMigratingBlobDB):

    def put(self, *args, **kw):
        return self.old_db.put(*args, **kw)


class PutInOldCopyToNewBlobDB(TemporaryMigratingBlobDB):

    def put(self, content, basename="", bucket=DEFAULT_BUCKET):
        info = self.old_db.put(content, basename, bucket)
        content.seek(0)
        self.copy_blob(content, info, bucket)
        return info


class FakeCouchDocument(mod.BlobMixin, Document):

    doc_type = "FakeCouchDocument"
    saved = False

    @classmethod
    def get_db(cls):
        class fake_db:
            dbname = "commcarehq_test"

            class server:
                @staticmethod
                def next_uuid():
                    return uuid.uuid4().hex
        return fake_db

    def save(self):
        self.saved = True


class FailingSaveCouchDocument(FakeCouchDocument):

    allow_saves = 1

    def save(self):
        if self.allow_saves:
            self.saved = True
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
