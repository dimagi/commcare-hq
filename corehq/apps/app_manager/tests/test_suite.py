# -*- coding: utf-8 -*-
import copy
import re
from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import (
    Application, AutoSelectCase, AUTO_SELECT_USER, AUTO_SELECT_CASE, LoadUpdateAction, AUTO_SELECT_FIXTURE,
    AUTO_SELECT_RAW, WORKFLOW_MODULE, DetailColumn, ScheduleVisit, FormSchedule, Module, AdvancedModule,
    WORKFLOW_ROOT, AdvancedOpenCaseAction, SortElement, PreloadAction, MappingItem, OpenCaseAction,
    OpenSubCaseAction, FormActionCondition, UpdateCaseAction, WORKFLOW_FORM, FormLink, AUTO_SELECT_USERCASE,
    ReportModule, ReportAppConfig)
from corehq.apps.app_manager.tests.util import TestFileMixin, commtrack_enabled
from corehq.apps.app_manager.xpath import (dot_interpolate, UserCaseXPath,
                                           interpolate_xpath, session_var)
from corehq.toggles import NAMESPACE_DOMAIN
from corehq.feature_previews import MODULE_FILTER
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache

from lxml import etree
import commcare_translations
from mock import patch
from corehq.apps.builds.models import BuildSpec


class SuiteTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        update_toggle_cache(MODULE_FILTER.slug, 'skelly', True, NAMESPACE_DOMAIN)
        update_toggle_cache(MODULE_FILTER.slug, 'domain', True, NAMESPACE_DOMAIN)
        update_toggle_cache(MODULE_FILTER.slug, 'example', True, NAMESPACE_DOMAIN)
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        self.is_usercase_in_use_mock.return_value = True

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()
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
        self._test_generic_suite_partial('suite-workflow', "./entry", 'suite-workflow-previous')

    def test_form_workflow_module(self):
        app = Application.wrap(self.get_json('suite-workflow'))
        for module in app.get_modules():
            for form in module.get_forms():
                form.post_form_workflow = WORKFLOW_MODULE

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module'), app.create_suite(), "./entry")

    def test_form_workflow_module_in_root(self):
        app = Application.wrap(self.get_json('suite-workflow'))
        for m in [1, 2]:
            module = app.get_module(m)
            module.put_in_root = True

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module-in-root'), app.create_suite(), "./entry")

    def test_form_workflow_root(self):
        app = Application.wrap(self.get_json('suite-workflow'))
        for module in app.get_modules():
            for form in module.get_forms():
                form.post_form_workflow = WORKFLOW_ROOT

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-root'), app.create_suite(), "./entry")

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
        json = self.get_json('suite-workflow')
        json['build_spec']['version'] = '2.20.0'

        app = Application.wrap(json)
        module = app.get_module(1)
        module.module_filter = "/mod/filter = '123'"
        self.assertXmlPartialEqual(
            self.get_xml('module-filter'),
            app.create_suite(),
            "./menu[@id='m1']"
        )

    def test_module_filter_with_session(self):
        json = self.get_json('suite-workflow')
        json['build_spec']['version'] = '2.20.0'

        app = Application.wrap(json)
        module = app.get_module(0)
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

    def _prep_case_list_form_app(self):
        app = Application.wrap(self.get_json('app'))
        case_module = app.get_module(0)
        case_module.get_form(0)

        register_module = app.add_module(Module.new_module('register', None))
        register_module.unique_id = 'register_case_module'
        register_module.case_type = case_module.case_type
        register_form = app.new_form(1, 'Register Case Form', lang='en')
        register_form.unique_id = 'register_case_form'
        register_form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        register_form.actions.open_case.condition.type = 'always'

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'New Case'
        }
        return app

    def test_case_list_registration_form(self):
        app = self._prep_case_list_form_app()
        case_module = app.get_module(0)
        case_module.case_list_form.media_image = 'jr://file/commcare/image/new_case.png'
        case_module.case_list_form.media_audio = 'jr://file/commcare/audio/new_case.mp3'
        self.assertXmlEqual(self.get_xml('case-list-form-suite'), app.create_suite())

    def test_case_list_registration_form_end_for_form_nav(self):
        app = self._prep_case_list_form_app()
        app.build_spec.version = '2.9'
        registration_form = app.get_module(1).get_form(0)
        registration_form.post_form_workflow = WORKFLOW_MODULE

        self.assertXmlPartialEqual(
            self.get_xml('case-list-form-suite-form-nav-entry'),
            app.create_suite(),
            "./entry[3]"
        )

    def test_case_list_registration_form_no_media(self):
        app = self._prep_case_list_form_app()
        self.assertXmlPartialEqual(
            self.get_xml('case-list-form-suite-no-media-partial'),
            app.create_suite(),
            "./detail[@id='m0_case_short']/action"
        )

    def test_case_list_registration_form_advanced(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        register_module = app.add_module(AdvancedModule.new_module('create', None))
        register_module.unique_id = 'register_module'
        register_module.case_type = 'dugong'
        register_form = app.new_form(0, 'Register Case', lang='en')
        register_form.unique_id = 'register_case_form'
        register_form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='dugong',
            case_tag='open_dugong',
            name_path='/data/name'
        ))

        case_module = app.add_module(AdvancedModule.new_module('update', None))
        case_module.unique_id = 'case_module'
        case_module.case_type = 'dugong'
        update_form = app.new_form(1, 'Update Case', lang='en')
        update_form.unique_id = 'update_case_form'
        update_form.actions.load_update_cases.append(LoadUpdateAction(
            case_type='dugong',
            case_tag='load_dugong',
            details_module=case_module.unique_id
        ))

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'Register another Dugong'
        }
        self.assertXmlEqual(self.get_xml('case-list-form-advanced'), app.create_suite())

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

    def test_case_list_lookup_wo_image(self):
        callout_action = "callout.commcarehq.org.dummycallout.LAUNCH"

        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = callout_action

        expected = """
            <partial>
                <lookup action="{}"/>
            </partial>
        """.format(callout_action)

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_w_image(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        image = "jr://file/commcare/image/callout"

        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = action
        module.case_details.short.lookup_image = image

        expected = """
            <partial>
                <lookup action="{}" image="{}"/>
            </partial>
        """.format(action, image)

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_w_name(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        image = "jr://file/commcare/image/callout"
        name = u"ιтѕ α тяαρ ʕ •ᴥ•ʔ"

        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = action
        module.case_details.short.lookup_image = image
        module.case_details.short.lookup_name = name

        expected = u"""
            <partial>
                <lookup name="{}" action="{}" image="{}"/>
            </partial>
        """.format(name, action, image)

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_w_extras_and_responses(self):
        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = "callout.commcarehq.org.dummycallout.LAUNCH"
        module.case_details.short.lookup_extras = [
            {'key': 'action_0', 'value': 'com.biometrac.core.SCAN'},
            {'key': "action_1", 'value': "com.biometrac.core.IDENTIFY"},
        ]
        module.case_details.short.lookup_responses = [
            {"key": "match_id_0"},
            {"key": "match_id_1"},
        ]

        expected = """
        <partial>
            <lookup action="callout.commcarehq.org.dummycallout.LAUNCH">
                <extra key="action_0" value="com.biometrac.core.SCAN"/>
                <extra key="action_1" value="com.biometrac.core.IDENTIFY"/>
                <response key="match_id_0"/>
                <response key="match_id_1"/>
            </lookup>
        </partial>
        """

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_disabled(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = False
        module.case_details.short.lookup_action = action
        module.case_details.short.lookup_responses = ["match_id_0", "left_index"]

        expected = "<partial></partial>"

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )


class ModuleAsChildTestBase(TestFileMixin):
    file_path = ('data', 'suite')
    child_module_class = None

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        update_toggle_cache(MODULE_FILTER.slug, self.app.domain, True, NAMESPACE_DOMAIN)
        self.module_0 = self.app.add_module(Module.new_module('parent', None))
        self.module_0.unique_id = 'm0'
        self.module_1 = self.app.add_module(self.child_module_class.new_module("child", None))
        self.module_1.unique_id = 'm1'

        for m_id in range(2):
            self.app.new_form(m_id, "Form", None)

        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()
        clear_toggle_cache(MODULE_FILTER.slug, self.app.domain, NAMESPACE_DOMAIN)

    def _load_case(self, child_module_form, case_type, parent_module=None):
        raise NotImplementedError()

    def test_basic_workflow(self):
        # make module_1 as submenu to module_0
        self.module_1.root_module_id = self.module_0.unique_id
        XML = """
        <partial>
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0"/>
          </menu>
          <menu root="m0" id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu")

    def test_workflow_with_put_in_root(self):
        # make module_1 as submenu to module_0
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_1.put_in_root = True

        XML = """
        <partial>
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0"/>
          </menu>
          <menu id="m0">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu")

    def test_child_module_session_datums_added(self):
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        m0f0.requires = 'case'
        m0f0.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        m0f0.actions.update_case.condition.type = 'always'
        m0f0.actions.subcases.append(OpenSubCaseAction(
            case_type='guppy',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'gold-fish')
        self._load_case(m1f0, 'guppy', parent_module=self.module_0)

        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums-added'), self.app.create_suite(), "./entry")

    def test_deleted_parent(self):
        self.module_1.root_module_id = "unknownmodule"

        cycle_error = {
            'type': 'unknown root',
        }
        errors = self.app.validate_app()
        self.assertIn(cycle_error, errors)

    def test_circular_relation(self):
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.root_module_id = self.module_1.unique_id
        cycle_error = {
            'type': 'root cycle',
        }
        errors = self.app.validate_app()
        self.assertIn(cycle_error, errors)


class AdvancedModuleAsChildTest(ModuleAsChildTestBase, SimpleTestCase):
    child_module_class = AdvancedModule

    def _load_case(self, child_module_form, case_type, parent_module=None):
        action = LoadUpdateAction(case_tag=case_type, case_type=case_type)
        if parent_module:
            action.parent_tag = parent_module.case_type

        child_module_form.actions.load_update_cases.append(action)

    def test_child_module_adjust_session_datums(self):
        """
        Test that session datum id's in child module match those in parent module
        """
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        m0f0.requires = 'case'
        m0f0.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        m0f0.actions.update_case.condition.type = 'always'

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'gold-fish')
        self._load_case(m1f0, 'guppy')
        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums'), self.app.create_suite(), "./entry")


class BasicModuleAsChildTest(ModuleAsChildTestBase, SimpleTestCase):
    child_module_class = Module

    def _load_case(self, child_module_form, case_type, parent_module=None):
        child_module_form.requires = 'case'
        child_module_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        child_module_form.actions.update_case.condition.type = 'always'

        if parent_module:
            module = child_module_form.get_module()
            module.parent_select.active = True
            module.parent_select.module_id = parent_module.unique_id

    def test_grandparent_as_child_module(self):
        """
        Module 0 case_type = gold-fish
        Module 1 case_type = guppy (child of gold-fish)
        Module 2 case_type = tadpole (child of guppy, grandchild of gold-fish)

        Module 2's parent module = Module 1
        """
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        self._load_case(m0f0, 'gold-fish')
        m0f0.actions.subcases.append(OpenSubCaseAction(
            case_type='guppy',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'guppy', parent_module=self.module_0)
        m1f0.actions.subcases.append(OpenSubCaseAction(
            case_type='tadpole',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_2 = self.app.add_module(self.child_module_class.new_module("grandchild", None))
        self.module_2.unique_id = 'm2'
        self.app.new_form(2, 'grandchild form', None)

        self.module_2.case_type = 'tadpole'
        m2f0 = self.module_2.get_form(0)
        self._load_case(m2f0, 'tadpole', parent_module=self.module_1)

        self.module_2.root_module_id = self.module_1.unique_id

        self.assertXmlPartialEqual(self.get_xml('child-module-grandchild-case'), self.app.create_suite(), "./entry")


class UserCaseOnlyModuleAsChildTest(BasicModuleAsChildTest):
    """
    Even though a module might be usercase-only, if it acts as a parent module
    then the user should still be prompted for a case of the parent module's
    case type.

    The rationale is that child cases of the usercase never need to be
    filtered by a parent module, because they can't be filtered any more than
    they already are; there is only one usercase.
    """

    def setUp(self):
        super(UserCaseOnlyModuleAsChildTest, self).setUp()
        self.is_usercase_in_use_mock.return_value = True

    def test_child_module_session_datums_added(self):
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        # m0 is a user-case-only module. m0f0 does not update a normal case, only the user case.
        m0f0.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'question1'})
        m0f0.actions.usercase_preload.condition.type = 'always'

        m0f0.actions.subcases.append(OpenSubCaseAction(
            case_type='guppy',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'gold-fish')
        self._load_case(m1f0, 'guppy', parent_module=self.module_0)

        self.assertXmlPartialEqual(
            self.get_xml('child-module-entry-datums-added-usercase'),
            self.app.create_suite(),
            "./entry"
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


class TestFormLinking(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')
    default_spec = {
        "m": [
            {
                "name": "m0",
                "type": "basic",
                "f": [
                    {"name": "m0f0", "actions": ["open"]}
                ]
            },
            {
                "name": "m1",
                "type": "basic",
                "f": [
                    {"name": "m1f0", "actions": ["update"]}
                ]
            }
        ]
    }

    def setUp(self):
        update_toggle_cache(MODULE_FILTER.slug, 'domain', True, NAMESPACE_DOMAIN)
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()
        clear_toggle_cache(MODULE_FILTER.slug, 'domain', NAMESPACE_DOMAIN)

    def make_app(self, spec):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec = BuildSpec.from_string('2.9.0/latest')
        case_type = "frog"
        for m_spec in spec["m"]:
            m_type = m_spec['type']
            m_class = Module if m_type == 'basic' else AdvancedModule
            module = app.add_module(m_class.new_module(m_spec['name'], None))
            module.unique_id = m_spec['name']
            module.case_type = m_spec.get("case_type", "frog")
            module.root_module_id = m_spec.get("parent", None)
            for f_spec in m_spec['f']:
                form_name = f_spec["name"]
                form = app.new_form(module.id, form_name, None)
                form.unique_id = form_name
                for a_spec in f_spec.get('actions', []):
                    if isinstance(a_spec, dict):
                        action = a_spec['action']
                        case_type = a_spec.get("case_type", case_type)
                        parent = a_spec.get("parent", None)
                    else:
                        action = a_spec
                    if 'open' == action:
                        if m_type == "basic":
                            form.actions.open_case = OpenCaseAction(name_path="/data/question1")
                            form.actions.open_case.condition.type = 'always'
                        else:
                            form.actions.open_cases.append(AdvancedOpenCaseAction(
                                case_type=case_type,
                                case_tag='open_{}'.format(case_type),
                                name_path='/data/name'
                            ))
                    elif 'update' == action:
                        if m_type == "basic":
                            form.requires = 'case'
                            form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
                            form.actions.update_case.condition.type = 'always'
                        else:
                            form.actions.load_update_cases.append(LoadUpdateAction(
                                case_type=case_type,
                                case_tag='update_{}'.format(case_type),
                                parent_tag=parent,
                            ))
                    elif 'open_subacse':
                        if m_type == "basic":
                            form.actions.subcases.append(OpenSubCaseAction(
                                case_type=case_type,
                                case_name="/data/question1",
                                condition=FormActionCondition(type='always')
                            ))
                        else:
                            form.actions.open_cases.append(AdvancedOpenCaseAction(
                                case_type=case_type,
                                case_tag='subcase_{}'.format(case_type),
                                name_path='/data/name',
                                parent_tag=parent
                            ))

        return app

    def test_basic(self):
        spec = copy.deepcopy(self.default_spec)
        spec["m"][0]["f"][0]["actions"] = []
        spec["m"][1]["f"][0]["actions"] = []
        app = self.make_app(spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", form_id=m1f0.unique_id)
        ]
        self.assertXmlPartialEqual(self.get_xml('form_link_basic'), app.create_suite(), "./entry[1]")

    def test_with_case_management_both_update(self):
        spec = copy.deepcopy(self.default_spec)
        spec["m"][0]["f"][0]["actions"] = ["update"]
        app = self.make_app(spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) > 7", form_id=m1f0.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_update_case'), app.create_suite(), "./entry[1]")

    def test_with_case_management_create_update(self):
        app = self.make_app(self.default_spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath='true()', form_id=m1f0.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_create_update_case'), app.create_suite(), "./entry[1]")

    def test_with_case_management_multiple_links(self):
        spec = copy.deepcopy(self.default_spec)
        spec["m"][1]["f"].append({"name": "m1f1", "actions": ["open"]})
        app = self.make_app(spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")
        m1f1 = app.get_form("m1f1")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="a = 1", form_id=m1f0.unique_id),
            FormLink(xpath="a = 2", form_id=m1f1.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_multiple'), app.create_suite(), "./entry[1]")

    def test_link_to_child_module(self):
        spec = {
            "m": [
                {
                    "name": "enroll child",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "enroll child", "actions": ["open"]}
                    ]
                },
                {
                    "name": "child visit module",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "followup", "actions": [
                            "update",
                            {"action": "open_subcase", "case_type": "visit"}
                        ]}
                    ]
                },
                {
                    "name": "visit history",
                    "type": "advanced",
                    "case_type": "visit",
                    "parent": "child visit module",
                    "f": [
                        {"name": "treatment", "actions": [
                            {"action": "update", "case_type": "child"},
                            {"action": "update", "case_type": "visit", "parent": "update_child"}
                        ]}
                    ]
                }
            ]
        }
        app = self.make_app(spec)

        m0f0 = app.get_form("enroll child")
        m1f0 = app.get_form("followup")
        m2f0 = app.get_form("treatment")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_tdh'), app.create_suite(), "./entry")

    def test_link_to_form_in_parent_module(self):
        spec = {
            "m": [
                {
                    "name": "enroll child",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "enroll child", "actions": ["open"]}
                    ]
                },
                {
                    "name": "child visit module",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "edit child", "actions": [
                            "update",
                        ]}
                    ]
                },
                {
                    "name": "visit history",
                    "type": "advanced",
                    "case_type": "visit",
                    "parent": "child visit module",
                    "f": [
                        {"name": "link to child", "actions": [
                            {"action": "update", "case_type": "child"},
                        ]}
                    ]
                }
            ]
        }
        app = self.make_app(spec)

        m1f1 = app.get_form("edit child")
        m2f1 = app.get_form("link to child")

        # link to child -> edit child
        m2f1.post_form_workflow = WORKFLOW_FORM
        m2f1.form_links = [
            FormLink(xpath="true()", form_id=m1f1.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_child_modules'), app.create_suite(), "./entry[3]")
