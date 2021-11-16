import uuid

from django.test import TestCase

from unittest.mock import patch

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqcase.analytics import get_number_of_cases_in_domain
from corehq.elastic import get_es_new
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.es.elasticsearch import ConnectionError
from corehq.util.test_utils import create_and_save_a_case, trap_extra_setup
from testapps.test_pillowtop.utils import process_pillow_changes

TEST_ES_META = {
    CASE_INDEX_INFO.index: CASE_INDEX_INFO
}


@es_test
class ESAccessorsTest(TestCase):
    domain = 'hqadmin-es-accessor'

    def setUp(self):
        super(ESAccessorsTest, self).setUp()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            initialize_index_and_mapping(self.elasticsearch, CASE_INDEX_INFO)
            initialize_index_and_mapping(self.elasticsearch, DOMAIN_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(CASE_INDEX_INFO.index)
        ensure_index_deleted(DOMAIN_INDEX_INFO.index)
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(ESAccessorsTest, self).tearDown()

    @patch('corehq.apps.hqcase.analytics.CaseES.index', CASE_INDEX_INFO.index)
    @patch('corehq.apps.es.es_query.ES_META', TEST_ES_META)
    @patch('corehq.elastic.ES_META', TEST_ES_META)
    def test_get_number_of_cases_in_domain(self):
        cases = [self._create_case_and_sync_to_es() for _ in range(4)]
        self.assertEqual(
            get_number_of_cases_in_domain(self.domain),
            len(cases)
        )

    def _create_case_and_sync_to_es(self):
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        with process_pillow_changes('case-pillow', {'skip_ucr': True}):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                create_and_save_a_case(self.domain, case_id, case_name)
        self.elasticsearch.indices.refresh(CASE_INDEX_INFO.index)
        return case_id, case_name
