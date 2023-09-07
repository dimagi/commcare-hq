from django.test import SimpleTestCase

import commcare_translations

from corehq.apps.app_manager.exceptions import UnknownInstanceError
from corehq.apps.app_manager.models import CustomAssertion
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class DefaultSuiteAssertionsTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_case_assertions(self, *args):
        self._test_generic_suite('app_case_sharing', 'suite-case-sharing')

    def test_no_case_assertions(self, *args):
        self._test_generic_suite('app_no_case_sharing', 'suite-no-case-sharing')


@patch_get_xform_resource_overrides()
class CustomSuiteAssertionsTest(SimpleTestCase, TestXmlMixin):
    _instance_declaration = """<partial><instance id="casedb" src="jr://instance/casedb"/></partial>"""

    def setUp(self):
        self._assertion_0 = "foo = 'bar' and baz = 'buzz'"
        self._assertion_1 = "count(instance('casedb')/casedb/case[@case_type='friend']) > 0"
        self._custom_assertions = [
            CustomAssertion(test=self._assertion_0, text={'en': "en-0", "fr": "fr-0"}),
            CustomAssertion(test=self._assertion_1, text={'en': "en-1", "fr": "fr-1"}),
        ]

    def _get_expected_xml(self, entity_code):
        return f"""
            <partial>
                <assertions>
                    <assert test="{self._assertion_0}">
                        <text>
                            <locale id="custom_assertion.{entity_code}.0"/>
                        </text>
                    </assert>
                    <assert test="{self._assertion_1}">
                        <text>
                            <locale id="custom_assertion.{entity_code}.1"/>
                        </text>
                    </assert>
                </assertions>
            </partial>
        """

    def _assert_translations(self, app, entity_code):
        en_app_strings = commcare_translations.loads(app.create_app_strings('en'))
        self.assertEqual(en_app_strings[f'custom_assertion.{entity_code}.0'], "en-0")
        self.assertEqual(en_app_strings[f'custom_assertion.{entity_code}.1'], "en-1")
        fr_app_strings = commcare_translations.loads(app.create_app_strings('fr'))
        self.assertEqual(fr_app_strings[f'custom_assertion.{entity_code}.0'], "fr-0")
        self.assertEqual(fr_app_strings[f'custom_assertion.{entity_code}.1'], "fr-1")

    def test_custom_form_assertions(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('m0', 'case1')
        form.custom_assertions = self._custom_assertions
        self.assertXmlPartialEqual(
            self._get_expected_xml('m0.f0'),
            factory.app.create_suite(),
            "entry/assertions"
        )
        self._assert_translations(factory.app, 'm0.f0')

    def test_custom_module_assertions(self, *args):
        factory = AppFactory(build_version='2.54.0')
        module, form = factory.new_basic_module('m0', 'case1')
        module.custom_assertions = self._custom_assertions
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            self._get_expected_xml('m0'),
            suite,
            "menu[@id='m0']/assertions"
        )
        self._assert_translations(factory.app, 'm0')
        self.assertXmlPartialEqual(
            self._instance_declaration, suite, "menu[@id='m0']/instance")

    def test_custom_app_assertions(self, *args):
        factory = AppFactory(build_version='2.54.0')
        module, form = factory.new_basic_module('m0', 'case1')
        factory.app.custom_assertions = self._custom_assertions
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            self._get_expected_xml('root'),
            suite,
            "menu[@id='root']/assertions"
        )
        self._assert_translations(factory.app, 'root')
        self.assertXmlPartialEqual(
            self._instance_declaration, suite, "menu[@id='root']/instance")

    def test_unknown_instance_reference(self, *args):
        factory = AppFactory(build_version='2.54.0')
        module, form = factory.new_basic_module('m0', 'case1')
        xpath = "instance('unknown')/thing/val = 1"
        factory.app.custom_assertions = [CustomAssertion(test=xpath, text={'en': "en-0"})]
        with self.assertRaises(UnknownInstanceError) as e:
            factory.app.create_suite()
        self.assertIn(xpath, str(e.exception))
