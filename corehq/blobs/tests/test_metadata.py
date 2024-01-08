from io import BytesIO
from uuid import uuid4

from django.test import TestCase

from corehq.blobs import CODES
from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.util import get_meta, new_meta, TemporaryFilesystemBlobDB
from corehq.form_processor.tests.utils import only_run_with_partitioned_database
from corehq.sql_db.util import (
    new_id_in_same_dbalias,
)


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
        query = BlobMeta.objects.partitioned_query(meta.parent_id)
        results = query.filter(id=meta.id).values_list('id', 'properties')
        self.assertEqual(list(results), [(meta.id, {})])

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

    def test_get_by_key(self):
        meta = self.db.put(BytesIO(b"cx"), meta=new_meta())
        copy = self.db.metadb.get(
            parent_id=meta.parent_id,
            key=meta.key
        )
        self.assertEqual(copy.key, meta.key)

    def test_get_missing_parent_id(self):
        meta = self.db.put(BytesIO(b"cx"), meta=new_meta())
        with self.assertRaises(TypeError):
            self.db.metadb.get(
                type_code=meta.type_code,
                name="",
            )

    def test_get_missing_type_code(self):
        meta = self.db.put(BytesIO(b"cx"), meta=new_meta())
        with self.assertRaises(TypeError):
            self.db.metadb.get(
                parent_id=meta.parent_id,
                name="",
            )

    def test_get_missing_name(self):
        meta = self.db.put(BytesIO(b"cx"), meta=new_meta())
        with self.assertRaises(TypeError):
            self.db.metadb.get(
                parent_id=meta.parent_id,
                type_code=meta.type_code,
            )

    def test_get_extra_arg(self):
        meta = self.db.put(BytesIO(b"cx"), meta=new_meta())
        with self.assertRaises(TypeError):
            self.db.metadb.get(
                parent_id=meta.parent_id,
                type_code=meta.type_code,
                name="",
                domain="test",
            )

    def test_get_missing_blobmeta(self):
        xid = uuid4().hex
        with self.assertRaises(BlobMeta.DoesNotExist):
            self.db.metadb.get(parent_id=xid, type_code=CODES.form_xml, name=xid)

    def test_get_missing_blobmeta_by_key(self):
        xid = uuid4().hex
        with self.assertRaises(BlobMeta.DoesNotExist):
            self.db.metadb.get(parent_id=xid, key=xid)

    def create_blobs(self):
        def put(parent_id, code):
            meta = new_meta(parent_id=parent_id, type_code=code)
            return self.db.put(BytesIO(b"cx"), meta=meta)

        class namespace(object):
            p1 = uuid4().hex
            p2 = uuid4().hex
            p3 = uuid4().hex
            m1 = put(p1, CODES.form_xml)
            m2 = put(p2, CODES.multimedia)
            m3 = put(p3, CODES.multimedia)

        return namespace

    def test_get_for_parent(self):
        ns = self.create_blobs()
        items = self.db.metadb.get_for_parent(ns.p1)
        self.assertEqual([x.key for x in items], [ns.m1.key])

    def test_get_for_parent_with_type_code(self):
        m1 = self.db.put(BytesIO(b"fx"), meta=new_meta(type_code=CODES.form_xml))
        m2 = self.db.put(BytesIO(b"cx"), meta=new_meta(type_code=CODES.multimedia))
        self.assertEqual(m1.parent_id, m2.parent_id)
        items = self.db.metadb.get_for_parent(m1.parent_id, CODES.form_xml)
        self.assertEqual([x.key for x in items], [m1.key])

    def test_get_for_parents(self):
        ns = self.create_blobs()
        items = self.db.metadb.get_for_parents([ns.p1, ns.p2])
        self.assertEqual({x.key for x in items}, {ns.m1.key, ns.m2.key})

    def test_get_for_parents_with_type_code(self):
        ns = self.create_blobs()
        items = self.db.metadb.get_for_parents(
            [ns.p1, ns.p2, ns.p3],
            CODES.multimedia,
        )
        self.assertEqual({x.key for x in items}, {ns.m2.key, ns.m3.key})

    def test_reparent(self):
        metadb = self.db.metadb
        self.db.put(BytesIO(b"content"), meta=new_meta(parent_id="no-change"))
        metas = []
        for name in "abc":
            meta = new_meta(parent_id="old", name=name)
            metas.append(self.db.put(BytesIO(b"content"), meta=meta))
        a, b, c = metas
        new_parent = new_id_in_same_dbalias("old")
        metadb.reparent("old", new_parent)
        self.assertEqual(metadb.get_for_parent("old"), [])
        self.assertEqual(
            [m.id for m in metadb.get_for_parent(new_parent)],
            [m.id for m in metas],
        )
        self.assertEqual(len(metadb.get_for_parent("no-change")), 1)


@only_run_with_partitioned_database
class TestPartitionedMetaDB(TestMetaDB):
    """MetaDB tests for partitioned database

    Extra cleanup is necessary because partition db operations are not
    done in a separate transaction per test.
    """

    def tearDown(self):
        # new_meta always uses the same parent_id by default
        metas = self.db.metadb.get_for_parent(new_meta().parent_id)
        self.db.bulk_delete(metas=metas)
        super(TestPartitionedMetaDB, self).tearDown()

    def create_blobs(self):
        def delete_blobs():
            self.db.bulk_delete(metas=[namespace.m1, namespace.m2, namespace.m3])

        namespace = super(TestPartitionedMetaDB, self).create_blobs()
        self.addCleanup(delete_blobs)
        return namespace
