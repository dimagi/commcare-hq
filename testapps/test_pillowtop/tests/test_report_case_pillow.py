import uuid

from django.test import TestCase, override_settings
from elasticsearch.exceptions import ConnectionError

from corehq.apps.es import CaseES
from corehq.apps.hqcase.management.commands.ptop_reindexer_v2 import reindex_and_clean
from corehq.elastic import get_es_new
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, create_and_save_a_case
from pillowtop.es_utils import initialize_index_and_mapping
from testapps.test_pillowtop.utils import process_pillow_changes

DOMAIN = 'report-case-pillowtest-domain'


@override_settings(ES_CASE_FULL_INDEX_DOMAINS=[DOMAIN])
class ReportCasePillowTest(TestCase):

    def setUp(self):
        super(ReportCasePillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            ensure_index_deleted(REPORT_CASE_INDEX_INFO.index)
            initialize_index_and_mapping(self.elasticsearch, REPORT_CASE_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(REPORT_CASE_INDEX_INFO.index)
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        super(ReportCasePillowTest, self).tearDown()

    @run_with_all_backends
    def test_report_case_pillow(self):
        case_id, case_name = self._create_case_and_sync_to_es(DOMAIN)

        # confirm change made it to elasticserach
        results = CaseES('report_cases').run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(DOMAIN, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])

    @run_with_all_backends
    def test_unsupported_domain(self):
        self._create_case_and_sync_to_es('unsupported-domain')

        results = CaseES('report_cases').run()
        self.assertEqual(0, results.total)

    def _create_case_and_sync_to_es(self, domain):
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        with process_pillow_changes('case-pillow'):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                create_and_save_a_case(domain, case_id, case_name)
        self.elasticsearch.indices.refresh(REPORT_CASE_INDEX_INFO.index)
        return case_id, case_name


@override_settings(ES_CASE_FULL_INDEX_DOMAINS=[DOMAIN])
class ReportCaseReindexerTest(TestCase):

    def setUp(self):
        super(ReportCaseReindexerTest, self).setUp()
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            ensure_index_deleted(REPORT_CASE_INDEX_INFO.index)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        ensure_index_deleted(REPORT_CASE_INDEX_INFO.index)
        super(ReportCaseReindexerTest, self).tearDown()

    @run_with_all_backends
    def test_report_case_reindexer(self):
        cases_included = set()
        for i in range(3):
            case = create_and_save_a_case(DOMAIN, uuid.uuid4().hex, 'case_name-{}'.format(i))
            cases_included.add(case.case_id)

        # excluded case
        create_and_save_a_case('unsupported', uuid.uuid4().hex, 'unsupported')

        reindex_and_clean('report-case')

        # verify there
        results = CaseES("report_cases").run()
        self.assertEqual(3, results.total, results.hits)
        ids_in_es = {doc['_id'] for doc in results.hits}
        self.assertEqual(cases_included, ids_in_es)
