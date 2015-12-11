import uuid
from django.test import SimpleTestCase
from pillowtop.feed.interface import Change
from pillowtop.listener import AliasedElasticPillow
from pillowtop.pillow.interface import PillowRuntimeContext
from .utils import require_explicit_elasticsearch_testing, get_doc_count


ES_VERSION = 0.9
# ES_VERSION = 1.0


class TestElasticPillow(AliasedElasticPillow):
    es_host = 'localhost'
    es_port = 9200
    es_alias = 'pillowtop_tests'
    es_type = 'test_doc'
    es_index = 'pillowtop_test_index'
    # just for the sake of something being here
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                }
            }
        }
    }
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

    @classmethod
    def calc_meta(cls):
        # must be overridden by subclasses of AliasedElasticPillow
        return cls.es_index


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
        # make sure it was created
        self.assertTrue(self.es.indices.exists(self.index))
        # check the subset of settings we expected to set
        settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        if ES_VERSION < 1.0:
            self.assertEqual('whitespace', settings_back['index.analysis.analyzer.default.tokenizer'])
            self.assertEqual('lowercase', settings_back['index.analysis.analyzer.default.filter.0'])
        else:

            self.assertEqual(
                pillow.es_meta['settings']['analysis'],
                settings_back['index']['analysis'],
            )
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

    def test_create_index_false_online_true(self):
        # this test use to raise a hard error so doesn't actually test anything
        pillow = TestElasticPillow(create_index=False)
        self.assertFalse(pillow.index_exists())
        self.assertFalse(pillow.mapping_exists())

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
        _send_doc_to_pillow(pillow, doc_id, doc)
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

    def test_send_bulk_empty(self):
        pillow = TestElasticPillow()
        # this used to fail hard before this test was added
        pillow.process_bulk([])
        self.assertEqual(0, get_doc_count(self.es, self.index))

    def test_assume_alias(self):
        pillow = TestElasticPillow()
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        _send_doc_to_pillow(pillow, doc_id, doc)
        self.assertEqual(1, get_doc_count(self.es, self.index))
        pillow.assume_alias()
        es_doc = self.es.get_source(pillow.es_alias, doc_id)
        for prop in doc:
            self.assertEqual(doc[prop], es_doc[prop])

    def test_assume_alias_deletes_old_aliases(self):
        # create a different index and set the alias for it
        pillow = TestElasticPillow()
        new_index = 'test-index-with-duplicate-alias'
        if not self.es.indices.exists(new_index):
            self.es.indices.create(index=new_index)
        self.es.indices.put_alias(new_index, pillow.es_alias)

        # make sure it's there in the other index
        aliases = self.es.indices.get_aliases()
        self.assertEqual([pillow.es_alias], aliases[new_index]['aliases'].keys())

        # assume alias and make sure it's removed (and added to the right index)
        pillow.assume_alias()
        aliases = self.es.indices.get_aliases()
        self.assertEqual(0, len(aliases[new_index]['aliases']))
        self.assertEqual([pillow.es_alias], aliases[self.index]['aliases'].keys())


def _send_doc_to_pillow(pillow, doc_id, doc):
    change = Change(
        id=doc_id,
        sequence_id=0,
        document=doc
    )
    pillow.processor(change, PillowRuntimeContext(do_set_checkpoint=False))
