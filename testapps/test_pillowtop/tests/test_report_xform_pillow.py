from django.test import override_settings, TestCase
from corehq.util.es.elasticsearch import ConnectionError

from corehq.apps.es import FormES
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from corehq.pillows.reportxform import ReportFormReindexerFactory
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, get_form_ready_to_save
from pillowtop.es_utils import initialize_index_and_mapping
from testapps.test_pillowtop.utils import process_pillow_changes

DOMAIN = 'report-xform-pillowtest-domain'


@override_settings(ES_XFORM_FULL_INDEX_DOMAINS=[DOMAIN])
class ReportXformPillowTest(TestCase):

    def setUp(self):
        super(ReportXformPillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_xforms()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            ensure_index_deleted(REPORT_XFORM_INDEX_INFO.index)
            initialize_index_and_mapping(self.elasticsearch, REPORT_XFORM_INDEX_INFO)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        ensure_index_deleted(REPORT_XFORM_INDEX_INFO.index)
        super(ReportXformPillowTest, self).tearDown()

    @run_with_all_backends
    def test_report_xform_pillow(self):
        form, metadata = self._create_form_and_sync_to_es(DOMAIN)

        # confirm change made it to elasticserach
        results = FormES("report_xforms").run()
        self.assertEqual(1, results.total, results.hits)
        form_doc = results.hits[0]
        self.assertEqual(DOMAIN, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
        self.assertEqual(form.form_id, form_doc['_id'])

    @run_with_all_backends
    def test_unsupported_domain(self):
        form, metadata = self._create_form_and_sync_to_es('unsupported-domain')

        # confirm change made it to elasticserach
        results = FormES("report_xforms").run()
        self.assertEqual(0, results.total)

    def _create_form_and_sync_to_es(self, domain):
        with process_pillow_changes('xform-pillow', {'skip_ucr': True}):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                metadata = TestFormMetadata(domain=domain)
                form = get_form_ready_to_save(metadata)
                FormProcessorInterface(domain=domain).save_processed_models([form])
        self.elasticsearch.indices.refresh(REPORT_XFORM_INDEX_INFO.index)
        return form, metadata


@override_settings(ES_XFORM_FULL_INDEX_DOMAINS=[DOMAIN])
class ReportXformReindexerTest(TestCase):

    def setUp(self):
        super(ReportXformReindexerTest, self).setUp()
        FormProcessorTestUtils.delete_all_xforms()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            ensure_index_deleted(REPORT_XFORM_INDEX_INFO.index)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        ensure_index_deleted(REPORT_XFORM_INDEX_INFO.index)
        super(ReportXformReindexerTest, self).tearDown()

    @run_with_all_backends
    def test_report_xform_reindexer(self):
        forms_included = set()
        for i in range(3):
            form = self._create_form(DOMAIN)
            forms_included.add(form.form_id)

        # excluded form
        self._create_form('unsupported')

        reindexer = ReportFormReindexerFactory().build()
        reindexer.reindex()

        # verify there
        results = FormES("report_xforms").run()
        self.assertEqual(3, results.total, results.hits)
        form_ids_in_es = {form_doc['_id'] for form_doc in results.hits}
        self.assertEqual(forms_included, form_ids_in_es)

    def _create_form(self, domain):
        metadata = TestFormMetadata(domain=domain)
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=domain).save_processed_models([form])
        return form
