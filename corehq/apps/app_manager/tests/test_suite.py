from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application, AutoSelectCase, AUTO_SELECT_USER, AUTO_SELECT_CASE, \
    LoadUpdateAction, AUTO_SELECT_FIXTURE, AUTO_SELECT_RAW, WORKFLOW_MODULE
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.app_manager.suite_xml import dot_interpolate

from lxml import etree
import commcare_translations


class SuiteTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def assertHasAllStrings(self, app, strings):
        et = etree.XML(app)
        locale_elems = et.findall(".//locale/[@id]")
        locale_strings = [elem.attrib['id'] for elem in locale_elems]

        app_strings = commcare_translations.loads(strings)

        for string in locale_strings:
            if string not in app_strings:
                raise AssertionError("App strings did not contain %s" % string)
            if not app_strings.get(string, '').strip():
                raise AssertionError("App strings has blank entry for %s" % string)

    def _test_generic_suite(self, app_tag, suite_tag=None):
        suite_tag = suite_tag or app_tag
        app = Application.wrap(self.get_json(app_tag))
        # print app.create_suite()
        self.assertXmlEqual(self.get_xml(suite_tag), app.create_suite())

    def _test_app_strings(self, app_tag):
        app = Application.wrap(self.get_json(app_tag))
        app_xml = app.create_suite()
        app_strings = app.create_app_strings('default')

        self.assertHasAllStrings(app_xml, app_strings)


    def test_normal_suite(self):
        self._test_generic_suite('app', 'normal-suite')

    def test_tiered_select(self):
        self._test_generic_suite('tiered-select', 'tiered-select')
    def test_3_tiered_select(self):
        self._test_generic_suite('tiered-select-3', 'tiered-select-3')

    def test_multisort_suite(self):
        self._test_generic_suite('multi-sort', 'multi-sort')

    def test_sort_only_value_suite(self):
        self._test_generic_suite('sort-only-value', 'sort-only-value')
        self._test_app_strings('sort-only-value')

    def test_callcenter_suite(self):
        self._test_generic_suite('call-center')

    def test_careplan_suite(self):
        self._test_generic_suite('careplan')

    def test_careplan_suite_own_module(self):
        app = Application.wrap(self.get_json('careplan'))
        app.get_module(1).display_separately = True
        self.assertXmlEqual(self.get_xml('careplan-own-module'), app.create_suite())

    def test_advanced_suite(self):
        self._test_generic_suite('suite-advanced')

    def test_advanced_suite_details(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        clinic_module_id = app.get_module(0).unique_id
        other_module_id = app.get_module(1).unique_id
        app.get_module(1).get_form(0).actions.load_update_cases[0].details_module = clinic_module_id
        app.get_module(1).get_form(1).actions.load_update_cases[0].details_module = other_module_id
        self.assertXmlEqual(self.get_xml('suite-advanced-details'), app.create_suite())

    def test_advanced_suite_commtrack(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.commtrack_enabled = True
        self.assertXmlEqual(self.get_xml('suite-advanced-commtrack'), app.create_suite())

    def test_advanced_suite_auto_select_user(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_USER,
            value_key='case_id'
        )
        self.assertXmlEqual(self.get_xml('suite-advanced-autoselect-user'), app.create_suite())

    def test_advanced_suite_auto_select_fixture(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_FIXTURE,
            value_source='table_tag',
            value_key='field_name'
        )
        self.assertXmlEqual(self.get_xml('suite-advanced-autoselect-fixture'), app.create_suite())

    def test_advanced_suite_auto_select_raw(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_RAW,
            value_key=("some xpath expression "
                       "containing instance('casedb') "
                       "and instance('commcaresession')")
        )
        self.assertXmlEqual(self.get_xml('suite-advanced-autoselect-raw'), app.create_suite())

    def test_advanced_suite_auto_select_case(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        load_update_cases = app.get_module(1).get_form(0).actions.load_update_cases
        load_update_cases.append(LoadUpdateAction(
            case_tag='auto_selected',
            auto_select=AutoSelectCase(
                mode=AUTO_SELECT_CASE,
                value_source=load_update_cases[0].case_tag,
                value_key='case_id_index'
            )
        ))
        self.assertXmlEqual(self.get_xml('suite-advanced-autoselect-case'), app.create_suite())

    def test_case_assertions(self):
        self._test_generic_suite('app_case_sharing', 'suite-case-sharing')

    def test_no_case_assertions(self):
        self._test_generic_suite('app_no_case_sharing', 'suite-no-case-sharing')

    def test_picture_format(self):
        self._test_generic_suite('app_picture_format', 'suite-picture-format')

    def test_audio_format(self):
        self._test_generic_suite('app_audio_format', 'suite-audio-format')

    def test_attached_picture(self):
        self._test_generic_suite('app_attached_image', 'suite-attached-image')

    def test_form_workflow_previous(self):
        """
        m0 - standard module - no case
            f0 - no case management
            f1 - no case management
        m1 - standard module - patient case
            f0 - register case
            f1 - update case
        m2 - standard module - patient case
            f0 - update case
            f1 - update case
        m3 - standard module - child case
            f0 - update child case
            f1 - update child case
        m4 - advanced module - patient case
            f0 - load a -> b
            f1 - load a -> b -> c
            f2 - load a -> b -> autoselect
        """
        self._test_generic_suite('suite-workflow', 'suite-workflow-previous')

    def test_form_workflow_module(self):
        app = Application.wrap(self.get_json('suite-workflow'))
        for module in app.get_modules():
            for form in module.get_forms():
                form.post_form_workflow = WORKFLOW_MODULE

        self.assertXmlEqual(self.get_xml('suite-workflow-module'), app.create_suite())

    def test_owner_name(self):
        self._test_generic_suite('owner-name')

    def test_form_filter(self):
        """
        Ensure form filter gets added correctly and appropriate instances get added to the entry.
        """
        app = Application.wrap(self.get_json('suite-advanced'))
        form = app.get_module(1).get_form(1)
        form.form_filter = "./edd = '123'"
        self.assertXmlEqual(self.get_xml('form-filter'), app.create_suite())


class RegexTest(SimpleTestCase):

    def testRegex(self):
        replacement = "@case_id stuff"
        cases = [
            ('./lmp < 570.5', '%s/lmp < 570.5'),
            ('stuff ./lmp < 570.', 'stuff %s/lmp < 570.'),
            ('.53 < hello.', '.53 < hello%s'),
        ]
        for case in cases:
            self.assertEqual(
                dot_interpolate(case[0], replacement),
                case[1] % replacement
            )