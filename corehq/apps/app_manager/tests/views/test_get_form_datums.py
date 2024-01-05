from django.http import Http404
from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.app_manager.views.forms import _get_form_link_datums


class TestReleaseBuild(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain_name = "fandago"

        factory = AppFactory(cls.domain_name, name="My App")
        m0, f0 = factory.new_basic_module("households", "household")
        f0.source = get_simple_form(xmlns=f0.unique_id)
        factory.form_requires_case(f0)

        m1, f1 = factory.new_basic_module("patients", "patient", parent_module=m0)
        factory.form_requires_case(f1)

        cls.app = factory.app
        cls.app.save()

        cls.module_id = m0.unique_id
        cls.child_module_id = m1.unique_id
        cls.form_id = f0.unique_id
        cls.disambiguated_form_id = f"{m0.unique_id}.{f0.unique_id}"

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        super().tearDownClass()

    def test_get_form_link_datums(self):
        datums = _get_form_link_datums(self.domain_name, self.app._id, self.disambiguated_form_id)
        self.assertEqual(datums, [{'name': 'case_id', 'case_type': 'household'}])

    def test_get_form_link_datums_wrong_domain(self):
        with self.assertRaises(Http404):
            _get_form_link_datums('other', self.app._id, self.disambiguated_form_id)

    def test_get_form_link_datums_missing_app_id(self):
        with self.assertRaises(Http404):
            _get_form_link_datums(self.domain_name, 'missing', self.disambiguated_form_id)

    def test_get_form_link_datums_missing_module_id(self):
        with self.assertRaises(Http404):
            _get_form_link_datums(self.domain_name, self.app._id, f'missing.{self.form_id}')

    def test_get_form_link_datums_missing_form_id(self):
        with self.assertRaises(Http404):
            _get_form_link_datums(self.domain_name, self.app._id, f'{self.module_id}.missing')

    def test_get_form_link_datums_for_module(self):
        datums = _get_form_link_datums(self.domain_name, self.app._id, self.module_id)
        self.assertEqual(datums, [{'name': 'case_id', 'case_type': 'household'}])

    def test_get_form_link_datums_for_child_module(self):
        datums = _get_form_link_datums(self.domain_name, self.app._id, self.child_module_id)
        self.assertEqual(datums, [{'name': 'case_id', 'case_type': 'patient'}])
