import uuid
from django.test import TestCase
from corehq.apps.reports.analytics.couchaccessors import guess_form_name_from_submissions_using_xmlns, \
    update_reports_analytics_indexes
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import TestFormMetadata, get_simple_form_xml
from corehq.form_processor.utils import convert_xform_to_json


class ReportsAnalyticsTest(TestCase):
    dependent_apps = ['couchforms', 'corehq.couchapps']

    def test_guess_form_name_from_xmlns_not_found(self):
        self.assertEqual(None, guess_form_name_from_submissions_using_xmlns('missing', 'missing'))

    def test_guess_form_name_from_xmlns(self):
        domain = uuid.uuid4().hex
        xmlns = uuid.uuid4().hex
        form_id = uuid.uuid4().hex
        form_name = 'my cool form'
        metadata = TestFormMetadata(domain=domain, xmlns=xmlns, form_name=form_name)
        form_json = convert_xform_to_json(get_simple_form_xml(form_id=form_id, metadata=metadata))
        interface = FormProcessorInterface(domain=metadata.domain)
        wrapped_form = interface.new_xform(form_json)
        wrapped_form.domain = domain
        interface.save_processed_models(wrapped_form, [wrapped_form])
        update_reports_analytics_indexes()
        self.assertEqual(form_name, guess_form_name_from_submissions_using_xmlns(domain, xmlns))
