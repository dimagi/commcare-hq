import uuid
from unittest.mock import patch

from django.test import TestCase

from elasticsearch.exceptions import ConnectionError

from pillow_retry.models import PillowError
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.es import CaseES, CaseSearchES
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    run_with_all_backends,
)
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import create_and_save_a_case, trap_extra_setup
from testapps.test_pillowtop.utils import process_pillow_changes


class CasePillowTest(TestCase):
    domain = 'case-pillowtest-domain'

    def setUp(self):
        super(CasePillowTest, self).setUp()
        self.process_case_changes = process_pillow_changes('DefaultChangeFeedPillow')
        self.process_case_changes.add_pillow('case-pillow', {'skip_ucr': True})
        FormProcessorTestUtils.delete_all_cases()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            initialize_index_and_mapping(self.elasticsearch, CASE_INDEX_INFO)
            initialize_index_and_mapping(self.elasticsearch, CASE_SEARCH_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(CASE_INDEX_INFO.index)
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        PillowError.objects.all().delete()
        super(CasePillowTest, self).tearDown()

    @run_with_all_backends
    def test_case_pillow(self):
        case_id, case_name = self._create_case_and_sync_to_es()

        # confirm change made it to elasticserach
        results = CaseES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])

    @run_with_all_backends
    def test_case_pillow_error_in_case_es(self):
        self.assertEqual(0, PillowError.objects.filter(pillow='case-pillow').count())
        with patch('corehq.pillows.case_search.domain_needs_search_index', return_value=True):
            with patch('corehq.pillows.case.transform_case_for_elasticsearch') as transform_patch:
                transform_patch.side_effect = Exception()
                case_id, case_name = self._create_case_and_sync_to_es()

        # confirm change did not make it to case search index
        results = CaseSearchES().run()
        self.assertEqual(0, results.total)

        # confirm change did not make it to case index
        results = CaseES().run()
        self.assertEqual(0, results.total)

        self.assertEqual(1, PillowError.objects.filter(pillow='case-pillow').count())

    @run_with_all_backends
    def test_case_soft_deletion(self):
        case_id, case_name = self._create_case_and_sync_to_es()

        # verify there
        results = CaseES().run()
        self.assertEqual(1, results.total)

        # soft delete the case
        with self.process_case_changes:
            CaseAccessors(self.domain).soft_delete_cases([case_id])
        self.elasticsearch.indices.refresh(CASE_INDEX_INFO.index)

        # ensure not there anymore
        results = CaseES().run()
        self.assertEqual(0, results.total)

    def _create_case_and_sync_to_es(self):
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        with self.process_case_changes:
            create_and_save_a_case(self.domain, case_id, case_name)
        self.elasticsearch.indices.refresh(CASE_INDEX_INFO.index)
        self.elasticsearch.indices.refresh(CASE_SEARCH_INDEX_INFO.index)
        return case_id, case_name
