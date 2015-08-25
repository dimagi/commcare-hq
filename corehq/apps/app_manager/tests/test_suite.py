# -*- coding: utf-8 -*-
from corehq.apps.app_manager.exceptions import CaseXPathValidationError
import re
from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import (
    AUTO_SELECT_CASE,
    AUTO_SELECT_FIXTURE,
    AUTO_SELECT_RAW,
    AUTO_SELECT_USER,
    AUTO_SELECT_USERCASE,
    AdvancedModule,
    Application,
    AutoSelectCase,
    DetailColumn,
    FormActionCondition,
    FormSchedule,
    LoadUpdateAction,
    MappingItem,
    Module,
    OpenCaseAction,
    OpenSubCaseAction,
    PreloadAction,
    ReportAppConfig,
    ReportModule,
    ScheduleVisit,
    SortElement,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestFileMixin, commtrack_enabled
from corehq.apps.app_manager.xpath import (
    dot_interpolate,
    UserCaseXPath,
    interpolate_xpath,
    session_var,
)
from corehq.toggles import NAMESPACE_DOMAIN
from corehq.feature_previews import MODULE_FILTER
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache

from lxml import etree
import commcare_translations
from mock import patch


class SuiteTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        update_toggle_cache(MODULE_FILTER.slug, 'skelly', True, NAMESPACE_DOMAIN)
        update_toggle_cache(MODULE_FILTER.slug, 'domain', True, NAMESPACE_DOMAIN)
        update_toggle_cache(MODULE_FILTER.slug, 'example', True, NAMESPACE_DOMAIN)
        self.suite_xml_is_usercase_in_use_patch = patch('corehq.apps.app_manager.suite_xml.is_usercase_in_use')
        self.suite_xml_is_usercase_in_use_mock = self.suite_xml_is_usercase_in_use_patch.start()
        self.suite_xml_is_usercase_in_use_mock.return_value = True

    def tearDown(self):
        self.suite_xml_is_usercase_in_use_patch.stop()
        clear_toggle_cache(MODULE_FILTER.slug, 'skelly', NAMESPACE_DOMAIN)
        clear_toggle_cache(MODULE_FILTER.slug, 'domain', NAMESPACE_DOMAIN)
        clear_toggle_cache(MODULE_FILTER.slug, 'example', NAMESPACE_DOMAIN)

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

    def _test_generic_suite_partial(self, app_tag, xpath, suite_tag=None):
        suite_tag = suite_tag or app_tag
        app = Application.wrap(self.get_json(app_tag))
        self.assertXmlPartialEqual(self.get_xml(suite_tag), app.create_suite(), xpath)

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

    def test_sort_cache_suite(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        detail = app.modules[0].case_details.short
        detail.sort_elements.append(
            SortElement(
                field=detail.columns[0].field,
                type='index',
                direction='descending',
            )
        )
        self.assertXmlPartialEqual(
            self.get_xml('sort-cache'),
            app.create_suite(),
            "./detail[@id='m0_case_short']"
        )

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

    @commtrack_enabled(True)
    def test_advanced_suite_commtrack(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        self.assertXmlEqual(self.get_xml('suite-advanced-commtrack'), app.create_suite())

    @commtrack_enabled(True)
    def test_autoload_supplypoint(self):
        app = Application.wrap(self.get_json('app'))
        app.modules[0].forms[0].source = re.sub('/data/plain',
                                                session_var('supply_point_id'),
                                                app.modules[0].forms[0].source)
        app_xml = app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('autoload_supplypoint'),
            app_xml,
            './entry[1]'
        )

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

    def test_case_assertions(self):
        self._test_generic_suite('app_case_sharing', 'suite-case-sharing')

    def test_no_case_assertions(self):
        self._test_generic_suite('app_no_case_sharing', 'suite-no-case-sharing')

    def _test_format(self, detail_format, template_form):
        app = Application.wrap(self.get_json('app_audio_format'))
        details = app.get_module(0).case_details
        details.short.get_column(0).format = detail_format
        details.long.get_column(0).format = detail_format

        expected = """
        <partial>
          <template form="{0}">
            <text>
              <xpath function="picproperty"/>
            </text>
          </template>
          <template form="{0}">
            <text>
              <xpath function="picproperty"/>
            </text>
          </template>
        </partial>
        """.format(template_form)
        self.assertXmlPartialEqual(expected, app.create_suite(), "./detail/field/template")

    def test_audio_format(self):
        self._test_format('audio', 'audio')

    def test_image_format(self):
        self._test_format('picture', 'image')

    def test_attached_picture(self):
        self._test_generic_suite_partial('app_attached_image', "./detail", 'suite-attached-image')

    def test_copy_form(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        module = app.add_module(AdvancedModule.new_module('module', None))
        original_form = app.new_form(module.id, "Untitled Form", None)
        original_form.source = '<source>'

        app._copy_form(module, original_form, module, rename=True)

        form_count = 0
        for f in app.get_forms():
            form_count += 1
            if f.unique_id != original_form.unique_id:
                self.assertEqual(f.name['en'], 'Copy of {}'.format(original_form.name['en']))
        self.assertEqual(form_count, 2, 'Copy form has copied multiple times!')

    def test_owner_name(self):
        self._test_generic_suite('owner-name')

    def test_form_filter(self):
        """
        Ensure form filter gets added correctly and appropriate instances get added to the entry.
        """
        app = Application.wrap(self.get_json('suite-advanced'))
        form = app.get_module(1).get_form(1)
        form.form_filter = "./edd = '123'"

        expected = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
            <command id="m1-f1" relevant="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_load_clinic0]/edd = '123'"/>
            <command id="m1-f2"/>
            <command id="m1-case-list"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, app.create_suite(), "./menu[@id='m1']")

    def test_module_filter(self):
        """
        Ensure module filter gets added correctly
        """
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec.version = '2.20.0'
        module = app.add_module(Module.new_module('m0', None))
        module.new_form('f0', None)

        module.module_filter = "/mod/filter = '123'"
        self.assertXmlPartialEqual(
            self.get_xml('module-filter'),
            app.create_suite(),
            "./menu[@id='m0']"
        )

    def test_module_filter_with_session(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec.version = '2.20.0'
        module = app.add_module(Module.new_module('m0', None))
        form = module.new_form('f0', None)
        form.xmlns = 'f0-xmlns'

        module.module_filter = "#session/user/mod/filter = '123'"
        self.assertXmlPartialEqual(
            self.get_xml('module-filter-user'),
            app.create_suite(),
            "./menu[@id='m0']"
        )
        self.assertXmlPartialEqual(
            self.get_xml('module-filter-user-entry'),
            app.create_suite(),
            "./entry[1]"
        )

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

    def test_usercase_id_added_update(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'

        child_form = app.new_form(0, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'
        child_form.actions.usercase_update = UpdateCaseAction(update={'name': '/data/question1'})
        child_form.actions.usercase_update.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_usercase_id_added_preload(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'

        child_form = app.new_form(0, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'
        child_form.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'name'})
        child_form.actions.usercase_preload.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_open_case_and_subcase(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        module = app.add_module(Module.new_module('parent', None))
        module.case_type = 'phone'
        module.unique_id = 'm0'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://m0-f0'
        form.actions.open_case = OpenCaseAction(name_path="/data/question1")
        form.actions.open_case.condition.type = 'always'
        form.actions.subcases.append(OpenSubCaseAction(
            case_type='tablet',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.assertXmlPartialEqual(self.get_xml('open_case_and_subcase'), app.create_suite(), "./entry[1]")

    def test_update_and_subcase(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        module = app.add_module(Module.new_module('parent', None))
        module.case_type = 'phone'
        module.unique_id = 'm0'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://m0-f0'
        form.requires = 'case'
        form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        form.actions.update_case.condition.type = 'always'
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=module.case_type,
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.assertXmlPartialEqual(self.get_xml('update_case_and_subcase'), app.create_suite(), "./entry[1]")

    def test_graphing(self):
        self._test_generic_suite('app_graphing', 'suite-graphing')

    def test_fixtures_in_graph(self):
        self._test_generic_suite('app_fixture_graphing', 'suite-fixture-graphing')

    def test_fixture_to_case_selection(self):
        factory = AppFactory(build_version='2.9')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = 'days'
        module.fixture_select.display_column = 'my_display_column'
        module.fixture_select.variable_column = 'my_variable_column'
        module.fixture_select.xpath = 'date(scheduled_date) <= date(today() + $fixture_value)'

        factory.form_updates_case(form)

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection'), factory.app.create_suite())

    def test_fixture_to_case_selection_parent_child(self):
        factory = AppFactory(build_version='2.9')

        m0, m0f0 = factory.new_basic_module('parent', 'parent')
        m0.fixture_select.active = True
        m0.fixture_select.fixture_type = 'province'
        m0.fixture_select.display_column = 'display_name'
        m0.fixture_select.variable_column = 'var_name'
        m0.fixture_select.xpath = 'province = $fixture_value'

        factory.form_updates_case(m0f0)

        m1, m1f0 = factory.new_basic_module('child', 'child')
        m1.fixture_select.active = True
        m1.fixture_select.fixture_type = 'city'
        m1.fixture_select.display_column = 'display_name'
        m1.fixture_select.variable_column = 'var_name'
        m1.fixture_select.xpath = 'city = $fixture_value'

        factory.form_updates_case(m1f0, parent_case_type='parent')

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection-parent-child'), factory.app.create_suite())

    def test_case_detail_tabs(self):
        self._test_generic_suite("app_case_detail_tabs", 'suite-case-detail-tabs')

    def test_case_tile_suite(self):
        self._test_generic_suite("app_case_tiles", "suite-case-tiles")

    def test_case_tile_pull_down(self):
        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.use_case_tiles = True
        module.case_details.short.persist_tile_on_forms = True
        module.case_details.short.pull_down_tile = True

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'a'},
                model='case',
                field='a',
                format='plain',
                case_tile_field='header'
            ),
            DetailColumn(
                header={'en': 'b'},
                model='case',
                field='b',
                format='plain',
                case_tile_field='top_left'
            ),
            DetailColumn(
                header={'en': 'c'},
                model='case',
                field='c',
                format='enum',
                enum=[
                    MappingItem(key='male', value={'en': 'Male'}),
                    MappingItem(key='female', value={'en': 'Female'}),
                ],
                case_tile_field='sex'
            ),
            DetailColumn(
                header={'en': 'd'},
                model='case',
                field='d',
                format='plain',
                case_tile_field='bottom_left'
            ),
            DetailColumn(
                header={'en': 'e'},
                model='case',
                field='e',
                format='date',
                case_tile_field='date'
            ),
        ]

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        self.assertXmlPartialEqual(
            self.get_xml('case_tile_pulldown_session'),
            app.create_suite(),
            "./entry/session"
        )

    def test_subcase_repeat_mixed(self):
        app = Application.new_app(None, "Untitled Application", application_version=APP_V2)
        module_0 = app.add_module(Module.new_module('parent', None))
        module_0.unique_id = 'm0'
        module_0.case_type = 'parent'
        form = app.new_form(0, "Form", None)

        form.actions.open_case = OpenCaseAction(name_path="/data/question1")
        form.actions.open_case.condition.type = 'always'

        child_case_type = 'child'
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=child_case_type,
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))
        # subcase in the middle that has a repeat context
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=child_case_type,
            case_name="/data/repeat/question1",
            repeat_context='/data/repeat',
            condition=FormActionCondition(type='always')
        ))
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=child_case_type,
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        expected = """
        <partial>
            <session>
              <datum id="case_id_new_parent_0" function="uuid()"/>
              <datum id="case_id_new_child_1" function="uuid()"/>
              <datum id="case_id_new_child_3" function="uuid()"/>
            </session>
        </partial>
        """
        self.assertXmlPartialEqual(expected,
                                   app.create_suite(),
                                   './entry[1]/session')

    def test_report_module(self):
        from corehq.apps.userreports.tests import get_sample_report_config

        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.unique_id = 'report_module'
        report = get_sample_report_config()
        report._id = 'd3ff18cd83adf4550b35db8d391f6008'

        report_app_config = ReportAppConfig(report_id=report._id,
                                            header={'en': 'CommBugz'})
        report_app_config._report = report
        report_module.report_configs = [report_app_config]
        report_module._loaded = True
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_menu'),
            app.create_suite(),
            "./menu",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_select_detail'),
            app.create_suite(),
            "./detail[@id='reports.d3ff18cd83adf4550b35db8d391f6008.select']",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_summary_detail'),
            app.create_suite(),
            "./detail[@id='reports.d3ff18cd83adf4550b35db8d391f6008.summary']",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_data_detail'),
            app.create_suite(),
            "./detail[@id='reports.d3ff18cd83adf4550b35db8d391f6008.data']",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_data_entry'),
            app.create_suite(),
            "./entry",
        )
        self.assertIn(
            'reports.d3ff18cd83adf4550b35db8d391f6008=CommBugz',
            app.create_app_strings('default'),
        )


class RegexTest(SimpleTestCase):

    def test_regex(self):
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

    def test_interpolate_xpath(self):
        replacements = {
            'case': "<casedb stuff>",
            'user': UserCaseXPath().case(),
            'session': "instance('commcaresession')/session",
        }
        cases = [
            ('./lmp < 570.5', '{case}/lmp < 570.5'),
            ('#case/lmp < 570.5', '{case}/lmp < 570.5'),
            ('stuff ./lmp < 570.', 'stuff {case}/lmp < 570.'),
            ('stuff #case/lmp < 570.', 'stuff {case}/lmp < 570.'),
            ('.53 < hello.', '.53 < hello{case}'),
            ('.53 < hello#case', '.53 < hello{case}'),
            ('#session/data/username', '{session}/data/username'),
            ('"jack" = #session/username', '"jack" = {session}/username'),
            ('./@case_id = #session/userid', '{case}/@case_id = {session}/userid'),
            ('#case/@case_id = #user/@case_id', '{case}/@case_id = {user}/@case_id'),
        ]
        for case in cases:
            self.assertEqual(
                interpolate_xpath(case[0], replacements['case']),
                case[1].format(**replacements)
            )

    def test_interpolate_xpath_error(self):
        for case in ('./lmp < 570.5', '#case/lmp < 570.5'):
            with self.assertRaises(CaseXPathValidationError):
                interpolate_xpath(case, None),


class FormFilterErrorTests(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.suite_xml_is_usercase_in_use_patch = patch('corehq.apps.app_manager.suite_xml.is_usercase_in_use')
        self.suite_xml_is_usercase_in_use_mock = self.suite_xml_is_usercase_in_use_patch.start()
        self.factory = AppFactory(build_version='2.9')

    def tearDown(self):
        self.suite_xml_is_usercase_in_use_patch.stop()

    def test_error_when_no_case(self):
        self.suite_xml_is_usercase_in_use_mock.return_value = True

        __, reg_form = self.factory.new_basic_module('reg_module', 'mother')
        self.factory.form_opens_case(reg_form)
        reg_form.form_filter = './due_date <= today()'

        with self.assertRaises(CaseXPathValidationError):
            self.factory.app.create_suite()

    def test_no_error_when_user_case(self):
        self.suite_xml_is_usercase_in_use_mock.return_value = True

        __, reg_form = self.factory.new_basic_module('reg_module', 'mother')
        self.factory.form_opens_case(reg_form)
        reg_form.form_filter = '#user/due_date <= today()'

        expected = """
        <partial>
            <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0" relevant="instance('casedb')/casedb/case[@case_type='commcare-user'][hq_user_id=instance('commcaresession')/session/context/userid][1]/due_date &lt;= today()"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, self.factory.app.create_suite(), './menu')

    def test_no_error_when_case(self):
        self.suite_xml_is_usercase_in_use_mock.return_value = False

        __, update_form = self.factory.new_basic_module('update_mother', 'mother')
        self.factory.form_updates_case(update_form)
        update_form.form_filter = '#case/due_date <= today()'

        expected = """
        <partial>
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0" relevant="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]/due_date &lt;= today()"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, self.factory.app.create_suite(), './menu')
