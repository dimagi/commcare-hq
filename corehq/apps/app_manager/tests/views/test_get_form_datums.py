from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.app_manager.views.forms import _get_form_datums


class TestReleaseBuild(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain_name = "fandago"

        factory = AppFactory(cls.domain_name, name="cheeto")
        m0, f0 = factory.new_basic_module("register", "cheeto")
        f0.source = get_simple_form(xmlns=f0.unique_id)
        factory.form_requires_case(f0)
        cls.app = factory.app
        cls.app.save()

        cls.module_id = m0.unique_id
        cls.form_id = f0.unique_id
        cls.disambiguated_form_id = f"{m0.unique_id}.{f0.unique_id}"

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        super().tearDownClass()

    def test_get_form_datums(self):
        datums = _get_form_datums(self.domain_name, self.app._id, self.disambiguated_form_id)
        self.assertEqual(datums, [{'name': 'case_id', 'case_type': 'cheeto'}])
