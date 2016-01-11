import copy
import uuid
from django.test import SimpleTestCase
from pillowtop.es_utils import INDEX_REINDEX_SETTINGS, INDEX_STANDARD_SETTINGS, update_settings, \
    set_index_reindex_settings, set_index_normal_settings, create_index_for_pillow, assume_alias_for_pillow, \
    pillow_index_exists, pillow_mapping_exists, completely_initialize_pillow_index
from pillowtop.feed.interface import Change
from pillowtop.listener import AliasedElasticPillow, send_to_elasticsearch, PillowtopIndexingError
from pillowtop.pillow.interface import PillowRuntimeContext
from django.conf import settings
from .utils import require_explicit_elasticsearch_testing, get_doc_count, get_index_mapping


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
        pillow = TestElasticPillow(online=False)
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
        if settings.ELASTICSEARCH_VERSION < 1.0:
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
        self.assertTrue(pillow_mapping_exists(pillow))
        mapping = get_index_mapping(self.es, self.index, pillow.es_type)
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
        pillow.get_es_new().indices.refresh(pillow.es_index)
        self.assertEqual(1, get_doc_count(self.es, self.index, refresh_first=False))

    def test_index_operations(self):
        pillow = TestElasticPillow()
        self.assertTrue(self.es.indices.exists(self.index))
        self.assertTrue(pillow_index_exists(pillow))

        # delete and check
        pillow.get_es_new().indices.delete(self.index)
        self.assertFalse(self.es.indices.exists(self.index))
        self.assertFalse(pillow_index_exists(pillow))

        # create and check
        create_index_for_pillow(pillow)
        self.assertTrue(self.es.indices.exists(self.index))
        self.assertTrue(pillow_index_exists(pillow))

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
        assume_alias_for_pillow(pillow)
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
        assume_alias_for_pillow(pillow)
        aliases = self.es.indices.get_aliases()
        self.assertEqual(0, len(aliases[new_index]['aliases']))
        self.assertEqual([pillow.es_alias], aliases[self.index]['aliases'].keys())

    def test_update_settings(self):
        TestElasticPillow()  # hack to create the index first
        update_settings(self.es, self.index, INDEX_REINDEX_SETTINGS)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_REINDEX_SETTINGS, index_settings_back, 'index')
        update_settings(self.es, self.index, INDEX_STANDARD_SETTINGS)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_STANDARD_SETTINGS, index_settings_back, 'index')

    def test_set_index_reindex(self):
        TestElasticPillow()  # hack to create the index first
        set_index_reindex_settings(self.es, self.index)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_REINDEX_SETTINGS, index_settings_back, 'index')

    def test_set_index_normal(self):
        TestElasticPillow()  # hack to create the index first
        set_index_normal_settings(self.es, self.index)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_STANDARD_SETTINGS, index_settings_back, 'index')

    def _compare_es_dicts(self, expected, returned, prefix):
        if settings.ELASTICSEARCH_VERSION < 1.0:
            for key, value in expected[prefix].items():
                self.assertEqual(str(value), returned['{}.{}'.format(prefix, key)])
        else:
            sub_returned = returned[prefix]
            for key, value in expected[prefix].items():
                split_key = key.split('.')
                returned_value = sub_returned[split_key[0]]
                for sub_key in split_key[1:]:
                    returned_value = returned_value[sub_key]
                self.assertEqual(str(value), returned_value)


def _send_doc_to_pillow(pillow, doc_id, doc):
    change = Change(
        id=doc_id,
        sequence_id=0,
        document=doc
    )
    pillow.processor(change, PillowRuntimeContext(do_set_checkpoint=False))


class TestSendToElasticsearch(SimpleTestCase):
    def setUp(self):
        self.pillow = TestElasticPillow(online=False)
        self.es = self.pillow.get_es_new()
        self.index = self.pillow.es_index

        # delete the index if it exists
        if self.es.indices.exists(self.index):
            self.es.indices.delete(self.index)
        self.assertFalse(self.es.indices.exists(self.index))

        completely_initialize_pillow_index(self.pillow)

    def test_create_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)

    def _send_to_es_and_check(self, doc, update=False, delete=False, esgetter=None):
        send_to_elasticsearch(
            index=self.index,
            doc_type=self.pillow.es_type,
            doc_id=doc['_id'],
            es_getter=esgetter or self.pillow.get_es_new,
            name='test',
            data=doc,
            update=update,
            delete=delete,
            except_on_failure=True,
            retries=1
        )

        if not delete:
            self.assertEqual(1, get_doc_count(self.es, self.index))
            es_doc = self.es.get_source(self.index, doc['_id'])
            for prop in doc:
                self.assertEqual(doc[prop], es_doc[prop])
        else:
            self.assertEqual(0, get_doc_count(self.es, self.index))

    def test_update_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        doc['property'] = 'bazz'
        self._send_to_es_and_check(doc, update=True)

    def test_delete_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        self._send_to_es_and_check(doc, delete=True)

    def test_connection_failure(self):
        def _bad_es_getter():
            from elasticsearch import Elasticsearch
            return Elasticsearch(
                [{
                    'host': 'localhost',
                    'port': '9000',  # bad port
                }],
                timeout=0,
            )

        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        with self.assertRaises(PillowtopIndexingError):
            self._send_to_es_and_check(doc, esgetter=_bad_es_getter)

    def test_not_found(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        self._send_to_es_and_check(doc, delete=True)
