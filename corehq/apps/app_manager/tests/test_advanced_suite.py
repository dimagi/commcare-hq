# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import (
    AUTO_SELECT_CASE,
    AUTO_SELECT_FIXTURE,
    AUTO_SELECT_RAW,
    AUTO_SELECT_USER,
    AUTO_SELECT_USERCASE,
    AdvancedModule,
    Application,
    AutoSelectCase,
    LoadCaseFromFixture,
    LoadUpdateAction,
    Module,
)
from corehq.apps.app_manager.tests.util import SuiteMixin, TestXmlMixin, commtrack_enabled
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.util.test_utils import flag_enabled


class AdvancedSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

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
        form.actions.load_update_cases[1].case_index.reference_id = 'custom-parent-ref'
        self.assertXmlPartialEqual(self.get_xml('custom-parent-ref'), app.create_suite(), "./entry[4]")

    def test_advanced_suite_case_list_filter(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        clinic_module = app.get_module(0)
        clinic_module.case_details.short.filter = "(filter = 'danny')"
        clinic_module_id = clinic_module.unique_id
        app.get_module(1).get_form(0).actions.load_update_cases[0].details_module = clinic_module_id

        req_module = app.get_module(2)
        req_module.case_details.short.filter = "filter = 'this'][other = 'that'"
        req_module_id = req_module.unique_id
        app.get_module(2).get_form(0).actions.load_update_cases[0].details_module = req_module_id

        self.assertXmlEqual(self.get_xml('suite-advanced-filter'), app.create_suite())

    def test_advanced_suite_auto_select_case_mobile(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).auto_select_case = True
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-case-mobile'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_user(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_USER,
            value_key='case_id'
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-user'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_fixture(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_FIXTURE,
            value_source='table_tag',
            value_key='field_name'
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-fixture'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_raw(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_RAW,
            value_key=("some xpath expression "
                       "containing instance('casedb') "
                       "and instance('commcaresession')")
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-raw'), app.create_suite(),
                                   './entry[2]')

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
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-case'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_usercase(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_USERCASE
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-usercase'), app.create_suite(),
                                   './entry[2]')

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
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-with-filter'), suite, './entry[2]')
        menu = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0" relevant="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_case_clinic]/edd = '123'"/>
            <command id="m1-f1"/>
            <command id="m1-f2"/>
            <command id="m1-case-list"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(menu, suite, "./menu[@id='m1']")

    def test_advanced_suite_load_case_from_fixture(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_tag="adherence",
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('item-list:table_tag')/calendar/year/month/day[@date > 735992 and @date < 736000]",
                fixture_tag="selected_date",
                fixture_variable="./@date",
                case_property="adherence_event_date",
                auto_select=True,
            )
        ))
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('load_case_from_fixture_session'), suite, './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_case_from_fixture_instance'), suite, './entry[2]/instance')

    def test_advanced_suite_load_case_from_fixture_with_arbitrary_datum(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_tag="adherence",
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('item-list:table_tag')/calendar/year/month/day[@date > 735992 and @date < 736000]",
                fixture_tag="selected_date",
                fixture_variable="./@date",
                case_property="adherence_event_date",
                auto_select=True,
                arbitrary_datum_id="extra_id",
                arbitrary_datum_function="extra_function()",
            )
        ))
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('load_case_from_fixture_arbitrary_datum'), suite,
                                   './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_case_from_fixture_instance'), suite, './entry[2]/instance')

    @flag_enabled('CUSTOM_CALENDAR_FIXTURE')
    def test_advanced_suite_load_case_from_fixture_with_custom_fixture(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_tag="adherence",
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('enikshay:calendar')/calendar/year/month/day[@date > 735992 and @date < 736000]",
                fixture_tag="selected_date",
                fixture_variable="./@date",
                case_property="adherence_event_date",
                auto_select=True,
            )
        ))
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('load_case_from_custom_fixture_session'), suite, './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_case_from_custom_fixture_instance'), suite, './entry[2]/instance')

    @flag_enabled('MOBILE_UCR')
    def test_advanced_suite_load_case_from_fixture_with_report_fixture(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_tag="",
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('commcare:reports')/reports/report[@id='some-report-guid']/rows/row",
                fixture_tag="selected_row",
                fixture_variable="./@index",
            )
        ))
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('load_case_from_report_fixture_session'), suite, './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_case_from_report_fixture_instance'), suite, './entry[2]/instance')

    def test_advanced_suite_load_from_fixture(self):
        nodeset = "instance('item-list:table_tag')/calendar/year/month/day[@date > 735992 and @date < 736000]"
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset=nodeset,
                fixture_tag="selected_date",
                fixture_variable="./@date",
                case_property="adherence_event_date",
                auto_select=True,
            )
        ))
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('load_from_fixture_session'), suite, './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_from_fixture_instance'), suite, './entry[2]/instance')

    def test_advanced_suite_load_from_fixture_auto_select(self):
        nodeset = "instance('item-list:table_tag')/calendar/year/month/day[@date > 735992 and @date < 736000]"
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset=nodeset,
                fixture_tag="selected_date",
                fixture_variable="./@date",
                auto_select_fixture=True,
                case_property="adherence_event_date",
                auto_select=True,
            )
        ))
        suite = app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('load_from_fixture_autoselect_session'),
            suite, './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_from_fixture_instance'), suite, './entry[2]/instance')

    def test_tiered_select_with_advanced_module_as_parent(self):
        app = Application.new_app('domain', "Untitled Application")

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

    def test_tiered_select_with_advanced_module_as_parent_with_filters(self):
        factory = AppFactory(build_version='2.25.0')
        parent_module, parent_form = factory.new_advanced_module('parent', 'parent')
        parent_module.case_details.short.filter = 'parent_filter = 1'

        child_module, child_form = factory.new_basic_module('child', 'child')
        child_form.xmlns = 'http://id_m1-f0'
        child_module.case_details.short.filter = 'child_filter = 1'
        factory.form_requires_case(child_form)

        # make child module point to advanced module as parent
        child_module.parent_select.active = True
        child_module.parent_select.module_id = parent_module.unique_id

        self.assertXmlPartialEqual(
            self.get_xml('advanced_module_parent_filters'),
            factory.app.create_suite(),
            "./entry[2]"
        )
