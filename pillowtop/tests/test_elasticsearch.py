import uuid
from django.test import SimpleTestCase
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
        # this is totally arbitrary, but something obscure enough that we can assume it worked
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


