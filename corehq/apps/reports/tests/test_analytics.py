import uuid
from django.test import TestCase
from corehq.apps.app_manager.tests import AppFactory
from corehq.apps.reports.analytics.couchaccessors import guess_form_name_from_submissions_using_xmlns, \
    update_reports_analytics_indexes, get_all_form_definitions_grouped_by_app_and_xmlns, FormInfo
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

    def test_get_all_form_definitions_grouped_by_app_and_xmlns_none(self):
        self.assertEqual([], get_all_form_definitions_grouped_by_app_and_xmlns('missing'))

    def test_get_all_form_definitions_grouped_by_app_and_xmlns(self):
        domain = uuid.uuid4().hex
        app_factory = AppFactory(domain=domain)
        module1, form1 = app_factory.new_basic_module('m1', 'test')
        module2, form2 = app_factory.new_basic_module('m2', 'test2')
        form1.xmlns = 'test1'
        form2.xmlns = 'test2'
        app_factory.app.save()
        update_reports_analytics_indexes()
        self.assertEqual(
            [FormInfo(app_factory.app._id, 'test1'), FormInfo(app_factory.app._id, 'test2')],
            get_all_form_definitions_grouped_by_app_and_xmlns(domain)
        )
