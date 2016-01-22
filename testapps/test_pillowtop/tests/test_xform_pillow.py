from unittest import skip
from django.test import TestCase, override_settings
from corehq.apps.es import FormES
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.xform import XFormPillow
from corehq.util.elastic import delete_es_index
from corehq.util.test_utils import get_form_ready_to_save


class XFormPillowTest(TestCase):

    domain = 'xform-pillowtest-domain'

    def setUp(self):
        FormProcessorTestUtils.delete_all_xforms()
        self.pillow = XFormPillow()
        delete_es_index(self.pillow.es_index)

    def test_xform_pillow_couch(self):
        metadata = TestFormMetadata(domain=self.domain)
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=self.domain).save_processed_models([form])
        self.pillow.process_changes(since=0, forever=False)
        self.pillow.get_es_new().indices.refresh(self.pillow.es_index)
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
        form.delete()

    @skip('This test will fail until sql pillows are hooked up to elastic')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_xform_pillow_sql(self):
        metadata = TestFormMetadata(domain=self.domain)
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=self.domain).save_processed_models([form])
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
        form.delete()
