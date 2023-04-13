from django.test import SimpleTestCase

import commcare_translations

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
    def setUp(self):
        _assertion_0 = "foo = 'bar' and baz = 'buzz'"
        _assertion_1 = "count(instance('casedb')/casedb/case[@case_type='friend']) > 0"
        self._custom_assertions = [
            CustomAssertion(test=_assertion_0, text={'en': "en-0", "fr": "fr-0"}),
            CustomAssertion(test=_assertion_1, text={'en': "en-1", "fr": "fr-1"}),
        ]
        self._assertions_xml = f"""
            <partial>
                <assertions>
                    <assert test="{_assertion_0}">
                        <text>
                            <locale id="custom_assertion.m0.f0.0"/>
                        </text>
                    </assert>
                    <assert test="{_assertion_1}">
                        <text>
                            <locale id="custom_assertion.m0.f0.1"/>
                        </text>
                    </assert>
                </assertions>
            </partial>
        """

    def test_custom_form_assertions(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('m0', 'case1')
        form.custom_assertions = self._custom_assertions
        self.assertXmlPartialEqual(
            self._assertions_xml,
            factory.app.create_suite(),
            "entry/assertions"
        )

        en_app_strings = commcare_translations.loads(module.get_app().create_app_strings('en'))
        self.assertEqual(en_app_strings['custom_assertion.m0.f0.0'], "en-0")
        self.assertEqual(en_app_strings['custom_assertion.m0.f0.1'], "en-1")
        fr_app_strings = commcare_translations.loads(module.get_app().create_app_strings('fr'))
        self.assertEqual(fr_app_strings['custom_assertion.m0.f0.0'], "fr-0")
        self.assertEqual(fr_app_strings['custom_assertion.m0.f0.1'], "fr-1")
