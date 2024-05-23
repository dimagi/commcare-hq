from unittest.mock import patch

from django.test import TestCase

from corehq.apps.es import const
from corehq.apps.es.case_search import (
    BulkActionItem,
    ElasticCaseSearch,
    case_search_adapter,
)
from corehq.apps.es.case_search_bha import case_search_bha_adapter
from corehq.apps.es.client import (
    ElasticMultiplexAdapter,
    create_document_adapter,
)
from corehq.apps.es.migration_operations import CreateIndex
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.tests.utils import create_case


@es_test(requires=[case_search_adapter], setup_class=True)
class TestFromPythonInCaseSearch(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'from-python-casesearch-tests'
        cls.case = create_case(cls.domain, save=True)

    def test_from_python_works_with_case_objects(self):
        case_search_adapter.from_python(self.case)

    def test_from_python_works_with_case_dicts(self):
        case_search_adapter.from_python(self.case.to_json())

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, case_search_adapter.from_python, set)

    def test_index_can_handle_case_dicts(self):
        case_dict = self.case.to_json()
        case_search_adapter.index(case_dict, refresh=True)
        self.addCleanup(case_search_adapter.delete, self.case.case_id)

        case = case_search_adapter.to_json(self.case)
        case.pop('@indexed_on')
        es_case = case_search_adapter.search({})['hits']['hits'][0]['_source']
        es_case.pop('@indexed_on')
        self.assertEqual(es_case, case)

    def test_index_can_handle_case_objects(self):
        case_search_adapter.index(self.case, refresh=True)
        self.addCleanup(case_search_adapter.delete, self.case.case_id)

        case = case_search_adapter.to_json(self.case)
        case.pop('@indexed_on')
        es_case = case_search_adapter.search({})['hits']['hits'][0]['_source']
        es_case.pop('@indexed_on')
        self.assertEqual(es_case, case)


@es_test(requires=[case_search_adapter, case_search_bha_adapter], setup_class=True)
class TestCaseSearchAdapterAlsoWritesToAnotherIndex(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'casesearch-dual-writetests'
        cls.case = create_case(cls.domain, save=True)
        cls.bulk_cases = [
            create_case(cls.domain, save=True).to_json()
            for i in range(2)
        ]
        cls.bulk_index_actions = [
            BulkActionItem.index(case)
            for case in cls.bulk_cases
        ]
        cls.bulk_delete_actions = [
            BulkActionItem.delete(case)
            for case in cls.bulk_cases
        ]

    def _get_normalized_cases_from_hits(self, cases):
        normalised_cases = []
        for hit in cases['hits']['hits']:
            normalised_case = self._normalise_case(hit['_source'])
            normalised_cases.append(normalised_case)
        return normalised_cases

    def _normalise_case(self, case):
        case.pop('@indexed_on')
        return case

    def test_index_writes_to_both_adapters(self):
        with patch('corehq.apps.es.case_search.multiplex_to_adapter', return_value=case_search_bha_adapter):
            case_search_adapter.index(self.case, refresh=True)
            self.addCleanup(case_search_bha_adapter.delete, self.case.case_id)
            self.addCleanup(case_search_adapter.delete, self.case.case_id)

        docs_in_bha = self._get_normalized_cases_from_hits(case_search_bha_adapter.search({}))
        docs_in_case_search = self._get_normalized_cases_from_hits(case_search_adapter.search({}))

        self.assertEqual(docs_in_bha, docs_in_case_search)

    def test_index_not_writes_to_bha_adapter_if_not_required(self):
        with patch('corehq.apps.es.case_search.multiplex_to_adapter', return_value=None):
            case_search_adapter.index(self.case, refresh=True)
            self.addCleanup(case_search_adapter.delete, self.case.case_id)

        docs_in_bha = self._get_normalized_cases_from_hits(case_search_bha_adapter.search({}))
        docs_in_case_search = self._get_normalized_cases_from_hits(case_search_adapter.search({}))

        self.assertEqual(docs_in_bha, [])
        self.assertEqual(len(docs_in_case_search), 1)

    def test_bulk_with_bha_mutliplexing(self):
        with patch('corehq.apps.es.case_search.multiplex_to_adapter', return_value=case_search_bha_adapter):
            case_search_adapter.bulk(self.bulk_index_actions, refresh=True)

        # Cleanup
        self.addCleanup(case_search_adapter.bulk, self.bulk_delete_actions, refresh=True)
        self.addCleanup(case_search_bha_adapter.bulk, self.bulk_delete_actions, refresh=True)

        docs_in_bha = self._get_normalized_cases_from_hits(case_search_bha_adapter.search({}))
        docs_in_case_search = self._get_normalized_cases_from_hits(case_search_adapter.search({}))

        self.assertEqual(docs_in_bha, docs_in_case_search)
        self.assertEqual(len(docs_in_case_search), 2)

    def test_bulk_without_bha_mutliplexing(self):
        with patch('corehq.apps.es.case_search.multiplex_to_adapter', return_value=None):
            case_search_adapter.bulk(self.bulk_index_actions, refresh=True)

        # Cleanup
        self.addCleanup(case_search_adapter.bulk, self.bulk_delete_actions, refresh=True)

        docs_in_bha = self._get_normalized_cases_from_hits(case_search_bha_adapter.search({}))
        docs_in_case_search = self._get_normalized_cases_from_hits(case_search_adapter.search({}))

        self.assertEqual(docs_in_bha, [])
        self.assertEqual(
            {case["case_id"] for case in self.bulk_cases},
            {case["_id"] for case in docs_in_case_search}
        )

    @patch.object(const, 'ES_CASE_SEARCH_INDEX_MULTIPLEXED', True)
    @patch('corehq.apps.es.case_search.multiplex_to_adapter', return_value=case_search_bha_adapter)
    def test_index_with_multiplexed_adapter(self, _):
        SECONDARY_INDEX = 'test_secondary_case_search_index'
        index_create_op = CreateIndex(
            SECONDARY_INDEX,
            case_search_adapter.type,
            case_search_adapter.mapping,
            case_search_adapter.analysis,
            case_search_adapter.settings_key,
        )
        index_create_op.run()
        self.addCleanup(index_create_op.reverse_run)
        cs_multiplex_adapter = create_document_adapter(
            ElasticCaseSearch,
            const.HQ_CASE_SEARCH_INDEX_NAME,
            case_search_adapter.type,
            # create document adapter appends test_ to the index name
            secondary=SECONDARY_INDEX[5:]
        )

        # Test we are using the multiplex adapter
        self.assertTrue(isinstance(cs_multiplex_adapter, ElasticMultiplexAdapter))

        # Index the case in ES
        cs_multiplex_adapter.index(self.case, refresh=True)
        self.addCleanup(case_search_adapter.delete, self.case.case_id)
        self.addCleanup(case_search_bha_adapter.delete, self.case.case_id, refresh=True)

        # Test index writes to all three indices i.e
        # primary, secondary and sub index
        docs_in_bha = self._get_normalized_cases_from_hits(case_search_bha_adapter.search({}))
        docs_in_case_search = self._get_normalized_cases_from_hits(case_search_adapter.search({}))
        docs_in_secondary_case_search = self._get_normalized_cases_from_hits(
            cs_multiplex_adapter.secondary.search({})
        )

        self.assertEqual(len(docs_in_case_search), 1)
        self.assertEqual(docs_in_bha, docs_in_case_search)
        self.assertEqual(docs_in_secondary_case_search, docs_in_case_search)

    @patch.object(const, 'ES_CASE_SEARCH_INDEX_MULTIPLEXED', True)
    @patch('corehq.apps.es.case_search.multiplex_to_adapter', return_value=None)
    def test_index_with_multiplexed_adapter_without_sub_index_settings(self, _):
        SECONDARY_INDEX = 'test_secondary_case_search_index'
        index_create_op = CreateIndex(
            SECONDARY_INDEX,
            case_search_adapter.type,
            case_search_adapter.mapping,
            case_search_adapter.analysis,
            case_search_adapter.settings_key,
        )
        index_create_op.run()
        self.addCleanup(index_create_op.reverse_run)
        cs_multiplex_adapter = create_document_adapter(
            ElasticCaseSearch,
            const.HQ_CASE_SEARCH_INDEX_NAME,
            case_search_adapter.type,
            # create document adapter appends test_ to the index name
            secondary=SECONDARY_INDEX[5:]
        )

        # Test we are using the multiplex adapter
        self.assertTrue(isinstance(cs_multiplex_adapter, ElasticMultiplexAdapter))

        # Index the case in ES
        cs_multiplex_adapter.index(self.case, refresh=True)
        self.addCleanup(case_search_adapter.delete, self.case.case_id)

        docs_in_bha = self._get_normalized_cases_from_hits(case_search_bha_adapter.search({}))
        docs_in_case_search = self._get_normalized_cases_from_hits(case_search_adapter.search({}))
        docs_in_secondary_case_search = self._get_normalized_cases_from_hits(
            cs_multiplex_adapter.secondary.search({})
        )

        # Test index writes to only two indices i.e
        # primary and secondary
        self.assertEqual(docs_in_bha, [])
        self.assertEqual(len(docs_in_case_search), 1)
        self.assertEqual(docs_in_secondary_case_search, docs_in_case_search)
