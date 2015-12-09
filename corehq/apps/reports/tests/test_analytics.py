import uuid
from django.test import TestCase
from corehq.apps.app_manager.tests import AppFactory
from corehq.apps.reports.analytics.couchaccessors import guess_form_name_from_submissions_using_xmlns, \
    update_reports_analytics_indexes, get_all_form_definitions_grouped_by_app_and_xmlns, FormInfo, \
    get_all_app_structures
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


class ReportAppAnalyticsTest(TestCase):
    dependent_apps = ['corehq.couchapps']

    @classmethod
    def setUpClass(cls):
        cls.domain = uuid.uuid4().hex
        cls.f1_xmlns = 'xmlns1'
        cls.f2_xmlns = 'xmlns2'
        cls.xmlnses = [cls.f1_xmlns, cls.f2_xmlns]
        app_factory = AppFactory(domain=cls.domain)
        module1, form1 = app_factory.new_basic_module('m1', '_casetype')
        module2, form2 = app_factory.new_basic_module('m2', '_casetype2')
        form1.xmlns = cls.f1_xmlns
        form2.xmlns = cls.f2_xmlns
        app_factory.app.save()
        cls.app = app_factory.app
        update_reports_analytics_indexes()

    def test_get_all_form_definitions_grouped_by_app_and_xmlns_no_data(self):
        self.assertEqual([], get_all_form_definitions_grouped_by_app_and_xmlns('missing'))

    def test_get_all_form_definitions_grouped_by_app_and_xmlns(self):
        self.assertEqual(
            [FormInfo(self.app._id, self.f1_xmlns), FormInfo(self.app._id, self.f2_xmlns)],
            get_all_form_definitions_grouped_by_app_and_xmlns(self.domain)
        )

    def test_get_all_app_structures_no_data(self):
        self.assertEqual([], get_all_app_structures('missing'))

    def test_get_all_app_structures(self):
        app_structures = get_all_app_structures(self.domain)
        self.assertEqual(2, len(app_structures))
        for i, app_structure in enumerate(app_structures):
            self.assertEqual(self.app._id, app_structure.app.id)
            self.assertEqual(i, app_structure.module.id)
            self.assertEqual(0, app_structure.form.id)
            self.assertEqual(self.xmlnses[i], app_structure.xmlns)
            self.assertFalse(app_structure.is_user_registration)
