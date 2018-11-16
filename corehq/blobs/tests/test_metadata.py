from __future__ import unicode_literals
from __future__ import absolute_import
from io import BytesIO
from uuid import uuid4

from django.db import connections
from django.test import TestCase

from corehq.blobs import CODES
from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.util import get_meta, new_meta, TemporaryFilesystemBlobDB
from corehq.form_processor.tests.utils import only_run_with_partitioned_database
from corehq.sql_db.util import get_db_alias_for_partitioned_doc


class TestMetaDB(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestMetaDB, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestMetaDB, cls).tearDownClass()

    def test_new(self):
        metadb = self.db.metadb
        with self.assertRaisesMessage(TypeError, "domain is required"):
            metadb.new()
        with self.assertRaisesMessage(TypeError, "parent_id is required"):
            metadb.new(domain="test")
        with self.assertRaisesMessage(TypeError, "type_code is required"):
            metadb.new(domain="test", parent_id="test")
        meta = metadb.new(
            domain="test",
            parent_id="test",
            type_code=CODES.multimedia,
        )
        self.assertEqual(meta.id, None)
        self.assertTrue(meta.key)

    def test_save_on_put(self):
        meta = new_meta()
        self.assertEqual(meta.id, None)
        self.db.put(BytesIO(b"content"), meta=meta)
        self.assertTrue(meta.id)
        saved = get_meta(meta)
        self.assertTrue(saved is not meta)
        self.assertEqual(saved.key, meta.key)

    def test_save_properties(self):
        meta = new_meta(properties={"mood": "Vangelis"})
        self.db.put(BytesIO(b"content"), meta=meta)
        self.assertEqual(get_meta(meta).properties, {"mood": "Vangelis"})

    def test_save_empty_properties(self):
        meta = new_meta()
        self.assertEqual(meta.properties, {})
        self.db.put(BytesIO(b"content"), meta=meta)
        self.assertEqual(get_meta(meta).properties, {})
        dbname = get_db_alias_for_partitioned_doc(meta.parent_id)
        with connections[dbname].cursor() as cursor:
            cursor.execute(
                "SELECT id, properties FROM blobs_blobmeta WHERE id = %s",
                [meta.id],
            )
            self.assertEqual(cursor.fetchall(), [(meta.id, None)])

    def test_delete(self):
        meta = new_meta()
        self.db.put(BytesIO(b"content"), meta=meta)
        self.db.delete(key=meta.key)
        with self.assertRaises(BlobMeta.DoesNotExist):
            get_meta(meta)

    def test_delete_missing_meta(self):
        meta = new_meta()
        self.assertFalse(self.db.exists(key=meta.key))
        # delete should not raise
        self.db.metadb.delete(meta.key, 0)

    def test_bulk_delete(self):
        metas = []
        for name in "abc":
            meta = new_meta(parent_id="parent", name=name)
            meta.content_length = 0
            metas.append(meta)
            self.db.metadb.put(meta)
        a, b, c = metas
        self.db.metadb.bulk_delete([a, b])
        for meta in [a, b]:
            with self.assertRaises(BlobMeta.DoesNotExist):
                get_meta(meta)
        get_meta(c)  # should not have been deleted

    def test_bulk_delete_unsaved_meta_raises(self):
        meta = new_meta()
        with self.assertRaises(ValueError):
            self.db.metadb.bulk_delete([meta])

    def test_get(self):
        meta = self.db.put(BytesIO(b"cx"), meta=new_meta())
        copy = self.db.metadb.get(
            parent_id=meta.parent_id,
            type_code=meta.type_code,
            name="",
        )
        self.assertEqual(copy.key, meta.key)

    def test_get_missing_blobmeta(self):
        xid = uuid4().hex
        with self.assertRaises(BlobMeta.DoesNotExist):
            self.db.metadb.get(parent_id=xid, type_code=CODES.form_xml, name=xid)


@only_run_with_partitioned_database
class TestPartitionedMetaDB(TestMetaDB):
    pass
