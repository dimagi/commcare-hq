import uuid
from django.test import SimpleTestCase
from pillowtop.feed.interface import Change
from pillowtop.listener import AliasedElasticPillow
from .utils import require_explicit_elasticsearch_testing, get_doc_count


class TestElasticPillow(AliasedElasticPillow):
    es_host = 'localhost'
    es_port = 9200
    es_alias = 'pillowtop_tests'
    es_type = 'test_doc'
    es_index = 'pillowtop_test_index'
    default_mapping = {
        '_meta': {
            'comment': 'You know, for tests',
            'created': '2015-10-07 @czue'
        },
        "properties": {
            "doc_type": {
                "index": "not_analyzed",
                "type": "string"
            },
        }
    }

    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determind md5
        """
        return self.es_index


class ElasticPillowTest(SimpleTestCase):

    @require_explicit_elasticsearch_testing
    def setUp(self):
        pillow = TestElasticPillow(create_index=False, online=False)
        self.index = pillow.es_index
        self.es = pillow.get_es_new()
        if self.es.indices.exists(self.index):
            self.es.indices.delete(self.index)
        self.assertFalse(self.es.indices.exists(self.index))

    def test_create_index_on_pillow_creation(self):
        pillow = TestElasticPillow()
        self.assertEqual(self.index, pillow.es_index)
        self.assertTrue(self.es.indices.exists(self.index))
        self.es.indices.delete(pillow.es_index)
        self.assertFalse(self.es.indices.exists(self.index))

    def test_mapping_initialization_on_pillow_creation(self):
        pillow = TestElasticPillow()
        mapping = pillow.get_index_mapping()[pillow.es_type]
        # we can't compare the whole dicts because ES adds a bunch of stuff to them
        self.assertEqual(
            pillow.default_mapping['properties']['doc_type']['index'],
            mapping['properties']['doc_type']['index']
        )

    def test_refresh_index(self):
        pillow = TestElasticPillow()
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        self.assertEqual(0, get_doc_count(self.es, self.index))
        self.es.create(self.index, 'case', doc, id=doc_id)
        self.assertEqual(0, get_doc_count(self.es, self.index, refresh_first=False))
        pillow.refresh_index()
        self.assertEqual(1, get_doc_count(self.es, self.index, refresh_first=False))

    def test_index_operations(self):
        pillow = TestElasticPillow()
        self.assertTrue(self.es.indices.exists(self.index))
        self.assertTrue(pillow.index_exists())

        # delete and check
        pillow.delete_index()
        self.assertFalse(self.es.indices.exists(self.index))
        self.assertFalse(pillow.index_exists())

        # create and check
        pillow.create_index()
        self.assertTrue(self.es.indices.exists(self.index))
        self.assertTrue(pillow.index_exists())

    def test_send_doc_to_es(self):
        pillow = TestElasticPillow()
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        change = Change(
            id=doc_id,
            sequence_id=0,
            document=doc
        )
        pillow.processor(change, False)
        self.assertEqual(1, get_doc_count(self.es, self.index))
        es_doc = self.es.get_source(self.index, doc_id)
        for prop in doc:
            self.assertEqual(doc[prop], es_doc[prop])

    def test_send_bulk(self):
        # this structure determined based on seeing what bulk_reindex does
        def make_bulk_row(doc):
            return {
                'key': [None, None, False],
                'doc': doc,
                'id': doc['_id'],
                'value': None
            }

        doc_ids = [uuid.uuid4().hex for i in range(3)]
        docs = [{'_id': doc_id, 'doc_type': 'MyCoolDoc', 'property': 'foo'} for doc_id in doc_ids]
        rows = [make_bulk_row(doc) for doc in docs]
        pillow = TestElasticPillow()
        pillow.process_bulk(rows)
        self.assertEqual(len(doc_ids), get_doc_count(self.es, self.index))
        for doc in docs:
            es_doc = self.es.get_source(self.index, doc['_id'])
            for prop in doc.keys():
                self.assertEqual(doc[prop], es_doc[prop])
