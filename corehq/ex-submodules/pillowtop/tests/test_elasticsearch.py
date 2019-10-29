import functools
import uuid

from django.conf import settings
from django.test import SimpleTestCase
from corehq.util.es.elasticsearch import ConnectionError

from corehq.elastic import get_es_instance, get_es_interface
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import (
    assume_alias,
    initialize_index,
    initialize_index_and_mapping,
    mapping_exists,
    set_index_normal_settings,
    set_index_reindex_settings,
)
from pillowtop.index_settings import INDEX_REINDEX_SETTINGS, INDEX_STANDARD_SETTINGS
from corehq.util.es.interface import ElasticsearchInterface
from pillowtop.exceptions import PillowtopIndexingError
from pillowtop.processors.elastic import send_to_elasticsearch
from .utils import get_doc_count, get_index_mapping, TEST_INDEX_INFO


class ElasticPillowTest(SimpleTestCase):

    def setUp(self):
        self.index = TEST_INDEX_INFO.index
        self.es = get_es_instance()
        self.es_interface = ElasticsearchInterface(self.es)
        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(self.index)

    def tearDown(self):
        ensure_index_deleted(self.index)

    def test_create_index(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        # make sure it was created
        self.assertTrue(self.es.indices.exists(self.index))
        # check the subset of settings we expected to set
        settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self.assertEqual(
            TEST_INDEX_INFO.meta['settings']['analysis'],
            settings_back['index']['analysis'],
        )
        self.es.indices.delete(self.index)
        self.assertFalse(self.es.indices.exists(self.index))

    def test_mapping_initialization(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        self.assertTrue(mapping_exists(self.es, TEST_INDEX_INFO))
        mapping = get_index_mapping(self.es, self.index, TEST_INDEX_INFO.type)
        # we can't compare the whole dicts because ES adds a bunch of stuff to them
        self.assertEqual(
            TEST_INDEX_INFO.mapping['properties']['doc_type']['index'],
            mapping['properties']['doc_type']['index']
        )

    def test_refresh_index(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        self.assertEqual(0, get_doc_count(self.es, self.index))
        self.es_interface.create_doc(self.index, 'case', doc_id, doc)
        self.assertEqual(0, get_doc_count(self.es, self.index, refresh_first=False))
        self.es.indices.refresh(self.index)
        self.assertEqual(1, get_doc_count(self.es, self.index, refresh_first=False))

    def test_index_operations(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        self.assertTrue(self.es.indices.exists(self.index))

        # delete and check
        self.es.indices.delete(self.index)
        self.assertFalse(self.es.indices.exists(self.index))

        # create and check
        initialize_index(self.es, TEST_INDEX_INFO)
        self.assertTrue(self.es.indices.exists(self.index))

    def test_assume_alias(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        send_to_elasticsearch(self.index, TEST_INDEX_INFO.type, doc_id, name='test', data=doc)
        self.assertEqual(1, get_doc_count(self.es, self.index))
        assume_alias(self.es, self.index, TEST_INDEX_INFO.alias)
        es_doc = self.es_interface.get_doc(TEST_INDEX_INFO.alias, TEST_INDEX_INFO.type, doc_id)
        for prop in doc:
            self.assertEqual(doc[prop], es_doc[prop])

    def test_assume_alias_deletes_old_aliases(self):
        # create a different index and set the alias for it
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        new_index = 'test_index-with-duplicate-alias'
        if not self.es.indices.exists(new_index):
            self.es.indices.create(index=new_index)
        self.es.indices.put_alias(new_index, TEST_INDEX_INFO.alias)
        self.addCleanup(functools.partial(ensure_index_deleted, new_index))

        # make sure it's there in the other index
        aliases = self.es.indices.get_aliases()
        self.assertEqual([TEST_INDEX_INFO.alias], list(aliases[new_index]['aliases']))

        # assume alias and make sure it's removed (and added to the right index)
        assume_alias(self.es, self.index, TEST_INDEX_INFO.alias)
        aliases = self.es.indices.get_aliases()
        self.assertEqual(0, len(aliases[new_index]['aliases']))
        self.assertEqual([TEST_INDEX_INFO.alias], list(aliases[self.index]['aliases']))

    def test_update_settings(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        self.es_interface.update_index_settings(self.index, INDEX_REINDEX_SETTINGS)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_REINDEX_SETTINGS, index_settings_back)
        self.es_interface.update_index_settings(self.index, INDEX_STANDARD_SETTINGS)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_STANDARD_SETTINGS, index_settings_back)

    def test_set_index_reindex(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        set_index_reindex_settings(self.es, self.index)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_REINDEX_SETTINGS, index_settings_back)

    def test_set_index_normal(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        set_index_normal_settings(self.es, self.index)
        index_settings_back = self.es.indices.get_settings(self.index)[self.index]['settings']
        self._compare_es_dicts(INDEX_STANDARD_SETTINGS, index_settings_back)

    def _compare_es_dicts(self, expected, returned):
        sub_returned = returned['index']
        should_not_exist = ElasticsearchInterface._disallowed_index_settings
        for key, value in expected['index'].items():
            if key in should_not_exist:
                continue
            split_key = key.split('.')
            returned_value = sub_returned[split_key[0]]
            for sub_key in split_key[1:]:
                returned_value = returned_value[sub_key]
            self.assertEqual(str(value), returned_value)

        for disallowed_setting in should_not_exist:
            self.assertNotIn(
                disallowed_setting, sub_returned,
                '{} is disallowed and should not be in the index settings'
                .format(disallowed_setting))


class TestSendToElasticsearch(SimpleTestCase):

    def setUp(self):
        self.es = get_es_instance()
        self.es_interface = ElasticsearchInterface(self.es)
        self.index = TEST_INDEX_INFO.index

        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(self.index)
            initialize_index_and_mapping(self.es, TEST_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(self.index)

    def test_create_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)

    def _send_to_es_and_check(self, doc, update=False, es_merge_update=False,
                              delete=False, es_interface=None):
        if update and es_merge_update:
            old_doc = self.es_interface.get_doc(self.index, TEST_INDEX_INFO.type, doc['_id'])

        send_to_elasticsearch(
            index=self.index,
            doc_type=TEST_INDEX_INFO.type,
            doc_id=doc['_id'],
            es_interface=es_interface or get_es_interface(),
            name='test',
            data=doc,
            update=update,
            es_merge_update=es_merge_update,
            delete=delete,
            retries=1
        )

        if not delete:
            self.assertEqual(1, get_doc_count(self.es, self.index))
            es_doc = self.es_interface.get_doc(self.index, TEST_INDEX_INFO.type, doc['_id'])
            if es_merge_update:
                old_doc.update(es_doc)
                for prop in doc:
                    self.assertEqual(doc[prop], old_doc[prop])
            else:
                for prop in doc:
                    self.assertEqual(doc[prop], es_doc[prop])
                self.assertTrue(all(prop in doc for prop in es_doc))
        else:
            self.assertEqual(0, get_doc_count(self.es, self.index))

    def test_update_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        doc['property'] = 'bazz'
        self._send_to_es_and_check(doc, update=True)

    def test_replace_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        del doc['property']
        self._send_to_es_and_check(doc, update=True)

    def test_merge_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        update = doc.copy()
        del update['property']
        update['new_prop'] = 'new_val'
        # merging should still keep old 'property'
        self._send_to_es_and_check(update, update=True, es_merge_update=True)

    def test_delete_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        self._send_to_es_and_check(doc, delete=True)

    def test_connection_failure(self):
        def _bad_es_interface():
            from corehq.util.es.elasticsearch import Elasticsearch
            return ElasticsearchInterface(Elasticsearch(
                [{
                    'host': settings.ELASTICSEARCH_HOST,
                    'port': settings.ELASTICSEARCH_PORT - 2,  # bad port
                }],
                timeout=0.1,
            ))

        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        with self.assertRaises(PillowtopIndexingError):
            self._send_to_es_and_check(doc, es_interface=_bad_es_interface())

    def test_not_found(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        self._send_to_es_and_check(doc, delete=True)

    def test_conflict(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)

        # attempt to create the same doc twice shouldn't fail
        self._send_to_es_and_check(doc)
