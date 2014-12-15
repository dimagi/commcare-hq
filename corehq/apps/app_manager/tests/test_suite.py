from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import (Application, AutoSelectCase,
    AUTO_SELECT_USER, AUTO_SELECT_CASE, LoadUpdateAction, AUTO_SELECT_FIXTURE,
    AUTO_SELECT_RAW, WORKFLOW_MODULE, DetailColumn, ScheduleVisit, FormSchedule,
    Module, AdvancedModule)
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

    def test_advanced_suite_parent_child_custom_ref(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        form = app.get_module(1).get_form(2)
        form.actions.load_update_cases[1].parent_reference_id = 'custom-parent-ref'
        self.assertXmlPartialEqual(self.get_xml('custom-parent-ref'), app.create_suite(), "./entry[4]")

    def test_advanced_suite_case_list_filter(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        clinic_module = app.get_module(0)
        clinic_module.case_details.short.filter = "(filter = 'danny')"
        clinic_module_id = clinic_module.unique_id
        app.get_module(1).get_form(0).actions.load_update_cases[0].details_module = clinic_module_id
        self.assertXmlEqual(self.get_xml('suite-advanced-filter'), app.create_suite())

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

    def test_advanced_suite_auto_select_with_filter(self):
        """
        Form filtering should be done using the last 'non-autoload' case being loaded.
        """
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_tag='autoload',
            auto_select=AutoSelectCase(
                mode=AUTO_SELECT_USER,
                value_key='case_id'
            )
        ))
        form = app.get_module(1).get_form(0)
        form.form_filter = "./edd = '123'"
        self.assertXmlEqual(self.get_xml('suite-advanced-autoselect-with-filter'), app.create_suite())

    def test_case_assertions(self):
        self._test_generic_suite('app_case_sharing', 'suite-case-sharing')

    def test_no_case_assertions(self):
        self._test_generic_suite('app_no_case_sharing', 'suite-no-case-sharing')

    def test_schedule(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        mod = app.get_module(1)
        mod.has_schedule = True
        f1 = mod.get_form(0)
        f2 = mod.get_form(1)
        f3 = mod.get_form(2)
        f1.schedule = FormSchedule(
            anchor='edd',
            expires=120,
            post_schedule_increment=15,
            visits=[
                ScheduleVisit(due=5, late_window=4),
                ScheduleVisit(due=10, late_window=9),
                ScheduleVisit(due=20, late_window=5)
            ]
        )

        f2.schedule = FormSchedule(
            anchor='dob',
            visits=[
                ScheduleVisit(due=7, late_window=4),
                ScheduleVisit(due=15)
            ]
        )

        f3.schedule = FormSchedule(
            anchor='dob',
            visits=[
                ScheduleVisit(due=9, late_window=1),
                ScheduleVisit(due=11)
            ]
        )
        mod.case_details.short.columns.append(
            DetailColumn(
                header={'en': 'Next due'},
                model='case',
                field='schedule:nextdue',
                format='plain',
            )
        )
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('schedule-fixture'), suite, './fixture')
        self.assertXmlPartialEqual(self.get_xml('schedule-entry'), suite, "./detail[@id='m1_case_short']")

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

    def test_form_workflow_root(self):
        # app = Application.wrap(self.get_json('suite-workflow-root'))
        
        app = Application.wrap(self.get_json('suite-workflow'))
        for m in [1, 2]:
            module = app.get_module(m)
            module.put_in_root = True

        self.assertXmlEqual(self.get_xml('suite-workflow-root'), app.create_suite())

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

    def test_tiered_select_with_advanced_module_as_parent(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        parent_module = app.add_module(AdvancedModule.new_module('parent', None))
        parent_module.case_type = 'parent'
        parent_module.unique_id = 'id_parent_module'

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'
        child_module.parent_select.active = True

        # make child module point to advanced module as parent
        child_module.parent_select.module_id = parent_module.unique_id

        child_form = app.new_form(1, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'

        self.assertXmlPartialEqual(self.get_xml('advanced_module_parent'), app.create_suite(), "./entry[1]")

    def test_graphing(self):
        self._test_generic_suite('app_graphing', 'suite-graphing')

    def test_case_detail_tabs(self):
        self._test_generic_suite("app_case_detail_tabs", 'suite-case-detail-tabs')


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
