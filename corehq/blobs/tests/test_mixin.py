from __future__ import unicode_literals
from hashlib import md5
from itertools import count
from unittest import TestCase
from StringIO import StringIO

import corehq.blobs.mixin as mod
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.util.test_utils import generate_cases
from dimagi.ext.couchdbkit import Document


class TestBlobMixin(TestCase):

    keys = (md5(str(k)).hexdigest() for k in count())

    @classmethod
    def setUpClass(cls):
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def make_doc(self, type_):
        return type_({
            "_id": next(self.keys),
            "_rev": next(self.keys),
        })

    def setUp(self):
        self.obj = self.make_doc(FakeCouchDocument)

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
        self.obj.delete_attachment(name)
        with self.assertRaises(mod.ResourceNotFound):
            self.obj.fetch_attachment(name)

    def test_document_blobs(self):
        name = "test.1"
        content = StringIO(b"content")
        self.obj.put_attachment(content, name, content_type="text/plain")
        self.assertEqual(self.obj.blobs[name].content_type, "text/plain")
        self.assertEqual(self.obj.blobs[name].content_length, 7)

    def test_fallback_on_fetch_fail(self):
        name = "test.1"
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments[name] = {"content": b"couch content"}
        self.assertEqual(doc.fetch_attachment(name), b"couch content")

    def test_fallback_on_delete_fail(self):
        name = "test.1"
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments[name] = {"content": b"couch content"}
        assert doc.delete_attachment(name), "couch attachment not deleted"
        assert name not in doc._attachments, doc._attachments

    def test_blobs_property(self):
        doc = self.make_doc(FallbackToCouchDocument)
        doc._attachments["att"] = {
            "content": b"couch content",
            "content_type": None,
            "length": 13,
        }
        doc.put_attachment("content", "blob", content_type="text/plain")
        self.assertIn("att", doc.blobs)
        self.assertIn("blob", doc.blobs)
        self.assertEqual(doc.blobs["att"].content_length, 13)
        self.assertEqual(doc.blobs["blob"].content_length, 7)


@generate_cases([
    (None, None),
    ("abc", None),
    (None, "abc"),
], TestBlobMixin)
def test_unsaved_document(self, _id, _rev):
    doc = {"_id": _id, "_rev": _rev}
    obj = FakeCouchDocument(doc)
    with self.assertRaises(mod.ResourceNotFound):
        obj.put_attachment(b"content", "test.1")


class FakeCouchDocument(mod.BlobMixin, Document):

    doc_type = "FakeCouchDocument"


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
    _migrating_from_couch = True
