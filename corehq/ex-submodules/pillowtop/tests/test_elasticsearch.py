import functools
import mock
import time
import uuid


from django.conf import settings
from django.test import SimpleTestCase
from unittest2 import skipIf

from corehq.util.es.elasticsearch import ConnectionError

from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqadmin.views.data import lookup_doc_in_es
from corehq.apps.es.forms import FormES
from corehq.elastic import get_es_new
from corehq.util.elastic import ensure_index_deleted, prefix_for_tests
from corehq.util.test_utils import trap_extra_setup
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.mappings.utils import transform_for_es7
from dimagi.utils.chunked import chunked
from pillowtop.es_utils import (
    assume_alias,
    initialize_index_and_mapping,
    mapping_exists,
    set_index_normal_settings,
    set_index_reindex_settings,
    MAX_DOCS,
)
from pillowtop.utils import build_bulk_payload
from pillowtop.index_settings import disallowed_settings_by_es_version, INDEX_REINDEX_SETTINGS, INDEX_STANDARD_SETTINGS
from corehq.util.es.interface import ElasticsearchInterface
from pillowtop.exceptions import PillowtopIndexingError
from pillowtop.processors.elastic import send_to_elasticsearch, get_indices_by_alias
from corehq.elastic import send_to_elasticsearch as send_to_es
from .utils import get_doc_count, get_index_mapping, TEST_INDEX_INFO


@es_test
class ElasticPillowTest(SimpleTestCase):

    def setUp(self):
        self.index = TEST_INDEX_INFO.index
        self.es_alias = TEST_INDEX_INFO.alias
        self.es = get_es_new()
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
            transform_for_es7(TEST_INDEX_INFO.mapping)['properties']['doc_type'],
            mapping['properties']['doc_type']
        )

    def test_refresh_index(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        self.assertEqual(0, get_doc_count(self.es, self.es_alias))
        self.es_interface.index_doc(self.es_alias, 'case', doc_id, doc)
        self.assertEqual(0, get_doc_count(self.es, self.es_alias, refresh_first=False))
        self.es.indices.refresh(self.index)
        self.assertEqual(1, get_doc_count(self.es, self.es_alias, refresh_first=False))

    def test_index_operations(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        self.assertTrue(self.es.indices.exists(self.index))

        # delete and check
        self.es.indices.delete(self.index)
        self.assertFalse(self.es.indices.exists(self.index))

        # create and check
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        self.assertTrue(self.es.indices.exists(self.index))

    def test_assume_alias(self):
        initialize_index_and_mapping(self.es, TEST_INDEX_INFO)
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        ElasticsearchInterface(get_es_new()).index_doc(
            self.index, TEST_INDEX_INFO.type, doc_id, {'doc_type': 'CommCareCase', 'type': 'mother'},
            verify_alias=False)
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
        aliases = self.es_interface.get_aliases()
        self.assertEqual([TEST_INDEX_INFO.alias], list(aliases[new_index]['aliases']))

        # assume alias and make sure it's removed (and added to the right index)
        assume_alias(self.es, self.index, TEST_INDEX_INFO.alias)
        aliases = self.es_interface.get_aliases()

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
        should_not_exist = disallowed_settings_by_es_version[settings.ELASTICSEARCH_MAJOR_VERSION]
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


TEST_ES_META = {
    TEST_INDEX_INFO.index: TEST_INDEX_INFO
}


@es_test
class TestSendToElasticsearch(SimpleTestCase):

    def setUp(self):
        self.es = get_es_new()
        self.es_interface = ElasticsearchInterface(self.es)
        self.index = TEST_INDEX_INFO.index
        self.es_alias = TEST_INDEX_INFO.alias

        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(self.index)
            initialize_index_and_mapping(self.es, TEST_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(self.index)

    @mock.patch('corehq.apps.hqadmin.views.data.ES_META', TEST_ES_META)
    @mock.patch('corehq.apps.es.es_query.ES_META', TEST_ES_META)
    @mock.patch('corehq.elastic.ES_META', TEST_ES_META)
    def test_create_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)
        res = lookup_doc_in_es(doc['_id'], self.index)
        self.assertEqual(res, doc)

    def _send_to_es_and_check(self, doc, update=False, es_merge_update=False,
                              delete=False, esgetter=None):
        if update and es_merge_update:
            old_doc = self.es_interface.get_doc(self.es_alias, TEST_INDEX_INFO.type, doc['_id'])

        send_to_elasticsearch(
            TEST_INDEX_INFO,
            doc_type=TEST_INDEX_INFO.type,
            doc_id=doc['_id'],
            es_getter=esgetter or get_es_new,
            name='test',
            data=doc,
            es_merge_update=es_merge_update,
            delete=delete
        )

        if not delete:
            self.assertEqual(1, get_doc_count(self.es, self.index))
            es_doc = self.es_interface.get_doc(self.es_alias, TEST_INDEX_INFO.type, doc['_id'])
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

    def test_missing_delete(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc, delete=True)

    def test_missing_merge(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        send_to_elasticsearch(
            TEST_INDEX_INFO,
            doc_type=TEST_INDEX_INFO.type,
            doc_id=doc['_id'],
            es_getter=get_es_new,
            name='test',
            data=doc,
            es_merge_update=True,
        )
        self.assertEqual(0, get_doc_count(self.es, self.index))

    def test_connection_failure(self):
        def _bad_es_getter():
            from corehq.util.es.elasticsearch import Elasticsearch
            return Elasticsearch(
                [{
                    'host': settings.ELASTICSEARCH_HOST,
                    'port': settings.ELASTICSEARCH_PORT - 2,  # bad port
                }],
                timeout=0.1,
            )

        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        with self.assertRaises(PillowtopIndexingError):
            self._send_to_es_and_check(doc, esgetter=_bad_es_getter)

    def test_not_found(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        self._send_to_es_and_check(doc, delete=True)

    def test_conflict(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)

        # attempt to create the same doc twice shouldn't fail
        self._send_to_es_and_check(doc)


@skipIf(settings.ELASTICSEARCH_MAJOR_VERSION != 7, 'Only applicable for ES7')
@es_test
class TestILM(SimpleTestCase):

    def setUp(self):
        self.es = get_es_new()
        self.es_interface = ElasticsearchInterface(self.es)
        self.index = XFORM_INDEX_INFO.index
        self.alias = XFORM_INDEX_INFO.alias
        XFORM_INDEX_INFO.ilm_config = prefix_for_tests(MAX_DOCS)
        self.es.cluster.put_settings({
            "persistent": {"indices.lifecycle.poll_interval": "1s"}
        })

        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(self.index)
            initialize_index_and_mapping(self.es, XFORM_INDEX_INFO)

    def tearDown(self):
        XFORM_INDEX_INFO.ilm_config = ""
        ensure_index_deleted(self.index)

    def rollover(self):
        # wait for ILM to kick in.
        #   Is double the poll_interval to provide enough buffer for ILM process
        time.sleep(2)

    def _send_to_es(self, docs):
        for chunk in chunked(docs, 2):
            # 2 is the max_docs per the policy
            for doc in chunk:
                send_to_es('forms', doc)
                self.es.indices.refresh(self.alias)
            self.rollover()

    def test_index_rollsover(self):
        #index should rollover 2 times making 3 total indices
        self._send_to_es([
            {"_id": "d1", "prop": "a"},
            {"_id": "d2", "prop": "b"},
            {"_id": "d3", "prop": "c"},
            {"_id": "d4", "prop": "d"},
            {"_id": "d5", "prop": "e"},
        ])
        self.assertEqual(
            len(get_indices_by_alias(self.alias)),
            3
        )
        self.assertEqual(
            FormES().remove_default_filters().ids_query(['d1', 'd4']).exclude_source().run().doc_ids,
            ['d1', 'd4']
        )
        self.assertEqual(
            FormES().remove_default_filters().count(),
            5
        )

    def test_repeated_insertions(self):
        # inserting the same doc shouldn't create duplicates
        #   and the index shouldn't rollover
        docs = [{"_id": "d1", "prop": "a"}] * 5
        self._send_to_es(docs)
        self.assertEqual(
            len(get_indices_by_alias(self.alias)),
            1
        )
        self.assertEqual(
            FormES().remove_default_filters().count(),
            1
        )

    def test_delete(self):
        docs = [
            {"_id": "d1", "prop": "a"},
            {"_id": "d2", "prop": "b"},
            {"_id": "d3", "prop": "c"},
        ]
        self._send_to_es(docs)
        send_to_es('forms', docs[1], delete=True)
        self.es.indices.refresh(self.alias)
        self.assertEqual(
            FormES().remove_default_filters().count(),
            2
        )

    def test_update_merge(self):
        docs = [
            {"_id": "d1", "prop": "a"},
            {"_id": "d2", "prop": "b"},
            {"_id": "d3", "prop": "c"},
        ]
        self._send_to_es(docs)
        docs[1].pop("prop")
        docs[1].update({"name": "new"})
        send_to_es('forms', docs[1], es_merge_update=True)
        self.es.indices.refresh(self.alias)
        self.assertEqual(
            FormES().remove_default_filters().ids_query(['d2']).run().hits,
            [{"prop": "b", "name": "new", "_id": "d2"}]
        )
        self.assertEqual(
            FormES().remove_default_filters().count(),
            3
        )

    def test_update(self):
        docs = [
            {"_id": "d1", "prop": "a"},
            {"_id": "d2", "prop": "b"},
            {"_id": "d3", "prop": "c"},
        ]
        self._send_to_es(docs)
        docs[1].update({"prop": "new"})
        send_to_es('forms', docs[1])
        self.es.indices.refresh(self.alias)
        self.assertEqual(
            FormES().remove_default_filters().ids_query(['d2']).run().hits,
            [{"prop": "new", "_id": "d2"}]
        )
        self.assertEqual(
            FormES().remove_default_filters().count(),
            3
        )

    def test_bulk_action(self):
        docs = [
            ({"_id": "d1", "prop": "a"}, False),
            ({"_id": "d2", "prop": "b"}, False),
            ({"_id": "d3", "prop": "c"}, False),
            ({"_id": "d4", "prop": "d"}, False),
            ({"_id": "d5", "prop": "e"}, False),
        ]
        changes = [MockChange(doc, deleted) for doc, deleted in docs]
        payload = build_bulk_payload(XFORM_INDEX_INFO, changes)
        self.es_interface.bulk_ops(payload)
        self.es.indices.refresh(self.alias)
        self.rollover()
        self.assertEqual(
            FormES().remove_default_filters().count(),
            5
        )

        # update doc1, delete doc 2
        docs = [
            ({"_id": "d1", "prop": "b"}, False),
            ({"_id": "d2", "prop": "b"}, True),
        ]
        changes = [MockChange(doc, deleted) for doc, deleted in docs]
        payload = build_bulk_payload(XFORM_INDEX_INFO, changes)
        self.es_interface.bulk_ops(payload)
        self.es.indices.refresh(self.alias)
        self.assertEqual(
            FormES().remove_default_filters().count(),
            4
        )
        self.assertEqual(
            FormES().remove_default_filters().ids_query(['d1']).run().hits,
            [{"prop": "b", "_id": "d1"}]
        )


class MockChange(object):

    def __init__(self, doc, delete=False):
        self.doc = doc
        self.id = doc['_id']
        self.delete = delete

    def get_document(self):
        return self.doc

    @property
    def deleted(self):
        return self.delete


@skipIf(settings.ELASTICSEARCH_MAJOR_VERSION != 7, 'Only applicable for ES7')
@es_test
class TestILMManualRollover(TestILM):

    def rollover(self):
        # Test that TestILM works also with manual rollover
        #   without having to wait for 2seconds for automatic ILM rollover
        # It's preferrable to use this rollover in other tests so that tests
        #   don't take lot of time waiting for ILM to kickover
        self.es.indices.rollover(self.alias, {'conditions': {'max_docs': 2}})
