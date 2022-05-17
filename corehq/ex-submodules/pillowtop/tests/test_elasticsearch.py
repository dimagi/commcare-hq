import functools
from unittest import mock
import uuid

from django.test import SimpleTestCase

from corehq.util.es.elasticsearch import ConnectionError, RequestError

from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqadmin.views.data import lookup_doc_in_es
from corehq.elastic import get_es_new
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, capture_log_output
from pillowtop.es_utils import (
    assume_alias,
    initialize_index,
    initialize_index_and_mapping,
    mapping_exists,
)
from corehq.util.es.interface import ElasticsearchInterface
from pillowtop.exceptions import PillowtopIndexingError
from pillowtop.processors.elastic import send_to_elasticsearch
from .utils import (
    TEST_INDEX_INFO,
    get_doc_count,
    get_index_mapping,
)


@es_test(index=TEST_INDEX_INFO)
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
            TEST_INDEX_INFO.mapping['properties']['doc_type'],
            mapping['properties']['doc_type']
        )

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
        ElasticsearchInterface(get_es_new()).index_doc(
            TEST_INDEX_INFO.alias,
            TEST_INDEX_INFO.type,
            doc_id,
            {'doc_type': 'CommCareCase', 'type': 'mother'},
        )
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
        # NOTE: alias is currently applied to *both* indices now because the
        # `initialize_index_and_mapping` helper function both creates the index
        # and applies an alias to the (new) index. The `assertIn()` test is used
        # here as to not make this test depend on that implied functionality of
        # the helper function.
        self.assertIn(new_index, aliases[TEST_INDEX_INFO.alias])

        # assume alias and make sure it's removed (and added to the right index)
        assume_alias(self.es, self.index, TEST_INDEX_INFO.alias)
        aliases = self.es_interface.get_aliases()

        self.assertEqual([self.index], aliases[TEST_INDEX_INFO.alias])


@es_test(index=TEST_INDEX_INFO)
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

    def test_create_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)
        res = lookup_doc_in_es(doc['_id'], self.es_alias)
        self.assertEqual(res, doc)

    def _send_to_es_and_check(self, doc, update=False, es_merge_update=False,
                              delete=False, esgetter=None):
        if update and es_merge_update:
            old_doc = self.es_interface.get_doc(self.es_alias, TEST_INDEX_INFO.type, doc['_id'])

        self._send_to_es(doc, es_merge_update=es_merge_update, delete=delete, esgetter=esgetter)

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

    def _send_to_es(self, doc, es_merge_update=False, delete=False,
                    esgetter=None):
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

    def test_connection_failure_no_error(self):
        logs = self._send_to_es_mock_errors(ConnectionError("test", "test", "test"), 2)
        self.assertIn("put_robust error", logs)
        self.assertIn("Max retry error", logs)

    def test_request_error(self):
        logs = self._send_to_es_mock_errors(RequestError("test", "test", "test"), 1)
        self.assertIn("put_robust error", logs)

    def _send_to_es_mock_errors(self, exception, retries):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        with mock.patch("pillowtop.processors.elastic._propagate_failure", return_value=False), \
             mock.patch("pillowtop.processors.elastic._retries", return_value=retries), \
             mock.patch("pillowtop.processors.elastic._sleep_between_retries"), \
             mock.patch("pillowtop.processors.elastic._get_es_interface") as _get_es_interface, \
             capture_log_output("pillowtop") as log:
            es_interface = mock.Mock()
            es_interface.index_doc.side_effect = exception
            _get_es_interface.return_value = es_interface
            send_to_elasticsearch(
                TEST_INDEX_INFO,
                doc_type=TEST_INDEX_INFO.type,
                doc_id=doc['_id'],
                es_getter=None,
                name='test',
                data=doc,
                es_merge_update=False,
                delete=False
            )
        return log.get_output()

    def test_not_found(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        self._send_to_es_and_check(doc, delete=True)

    def test_conflict(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)

        # attempt to create the same doc twice shouldn't fail
        self._send_to_es_and_check(doc)

    def test_retry_on_conflict_absent_on_index(self):
        args, kw = self._send_to_es_and_get_interface_args(False, "index_doc")
        self.assertNotIn("retry_on_conflict", kw.get("params", {}))

    def test_retry_on_conflict_present_on_update(self):
        args, kw = self._send_to_es_and_get_interface_args(True, "update_doc_fields")
        self.assertIn("retry_on_conflict", kw.get("params", {}))

    def _send_to_es_and_get_interface_args(self, update, method):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        path = f"pillowtop.processors.elastic.ElasticsearchInterface.{method}"
        with mock.patch(path) as mock_meth:
            self._send_to_es(doc, es_merge_update=update)
            mock_meth.assert_called_once()
            return mock_meth.call_args
