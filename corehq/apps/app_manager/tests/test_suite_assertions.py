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
class SuiteAssertionsTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def test_case_assertions(self, *args):
        self._test_generic_suite('app_case_sharing', 'suite-case-sharing')

    def test_no_case_assertions(self, *args):
        self._test_generic_suite('app_no_case_sharing', 'suite-no-case-sharing')

    def test_custom_assertions(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('m0', 'case1')

        tests = ["foo = 'bar' and baz = 'buzz'", "count(instance('casedb')/casedb/case[@case_type='friend']) > 0"]

        form.custom_assertions = [
            CustomAssertion(test=test, text={'en': "en-{}".format(id), "fr": "fr-{}".format(id)})
            for id, test in enumerate(tests)
        ]
        assertions_xml = [
            """
                <assert test="{test}">
                    <text>
                        <locale id="custom_assertion.m0.f0.{id}"/>
                    </text>
                </assert>
            """.format(test=test, id=id) for id, test in enumerate(tests)
        ]
        self.assertXmlPartialEqual(
            """
            <partial>
                <assertions>
                    {assertions}
                </assertions>
            </partial>
            """.format(assertions="".join(assertions_xml)),
            factory.app.create_suite(),
            "entry/assertions"
        )

        en_app_strings = commcare_translations.loads(module.get_app().create_app_strings('en'))
        self.assertEqual(en_app_strings['custom_assertion.m0.f0.0'], "en-0")
        self.assertEqual(en_app_strings['custom_assertion.m0.f0.1'], "en-1")
        fr_app_strings = commcare_translations.loads(module.get_app().create_app_strings('fr'))
        self.assertEqual(fr_app_strings['custom_assertion.m0.f0.0'], "fr-0")
        self.assertEqual(fr_app_strings['custom_assertion.m0.f0.1'], "fr-1")
