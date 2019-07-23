# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib
import mock
import re
from lxml.etree import tostring

from django.test import SimpleTestCase

from corehq.apps.app_manager.exceptions import SuiteValidationError, DuplicateInstanceIdError
from corehq.apps.app_manager.schemas.document.form_action import (
    FormActionCondition,
    OpenCaseAction,
    PreloadAction,
    UpdateCaseAction,
    OpenSubCaseAction,
)
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
    GraphConfiguration,
    GraphSeries,
    MappingItem,
    Module,
    ReportAppConfig,
    ReportModule,
    SortElement,
    CustomInstance,
    CustomAssertion,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import SuiteMixin, TestXmlMixin, commtrack_enabled, parse_normalize
from corehq.apps.app_manager.xpath import (
    session_var,
)
from corehq.apps.hqmedia.models import HQMediaMapItem
from corehq.apps.locations.models import LocationFixtureConfiguration
from corehq.apps.userreports.models import ReportConfiguration
from corehq.util.test_utils import flag_enabled
import commcare_translations


class SuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    @staticmethod
    def _add_columns_for_case_details(_module):
        _module.case_details.short.columns = [
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

    def ensure_module_session_datum_xml(self, factory, detail_inline_attr, detail_persistent_attr):
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    {detail_confirm_attr}
                    {detail_inline_attr}
                    {detail_persistent_attr}
                    detail-select="m1_case_short"
                    id="case_id_load_person_0"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """.format(detail_confirm_attr='detail-confirm="m1_case_long"' if not detail_inline_attr else '',
                       detail_inline_attr=detail_inline_attr,
                       detail_persistent_attr=detail_persistent_attr),
            suite,
            'entry/command[@id="m1-f0"]/../session/datum',
        )

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
                blanks='first',
            )
        )
        self.assertXmlPartialEqual(
            self.get_xml('sort-cache'),
            app.create_suite(),
            "./detail[@id='m0_case_short']"
        )

    def test_sort_cache_search(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.modules[0].search_config = CaseSearch(
            properties=[CaseSearchProperty(name='name', label={'en': 'Name'})],
        )
        detail = app.modules[0].case_details.short
        detail.sort_elements.append(
            SortElement(
                field=detail.columns[0].field,
                type='index',
                direction='descending',
                blanks='first',
            )
        )
        self.assertXmlPartialEqual(
            self.get_xml('sort-cache-search'),
            app.create_suite(),
            "./detail[@id='m0_search_short']"
        )

    def test_sort_calculation(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        detail = app.modules[0].case_details.short
        detail.sort_elements.append(
            SortElement(
                field=detail.columns[0].field,
                type='string',
                direction='descending',
                blanks='first',
                sort_calculation='random()'
            )
        )
        sort_node = """
        <partial>
            <sort direction="descending" blanks="first" order="1" type="string">
              <text>
                <xpath function="random()"/>
              </text>
            </sort>
        </partial>
        """
        self.assertXmlPartialEqual(
            sort_node,
            app.create_suite(),
            "./detail[@id='m0_case_short']/field/sort"
        )

    def test_callcenter_suite(self):
        self._test_generic_suite('call-center')

    @commtrack_enabled(True)
    def test_product_list_custom_data(self):
        # product data shouldn't be interpreted as a case index relationship
        app = Application.wrap(self.get_json('suite-advanced'))
        custom_path = 'product_data/is_bedazzled'
        app.modules[1].product_details.short.columns[0].field = custom_path
        suite_xml = app.create_suite()
        for xpath in ['/template/text/xpath', '/sort/text/xpath']:
            self.assertXmlPartialEqual(
                '<partial><xpath function="{}"/></partial>'.format(custom_path),
                suite_xml,
                './detail[@id="m1_product_short"]/field[1]'+xpath,
            )

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

    def test_case_assertions(self):
        self._test_generic_suite('app_case_sharing', 'suite-case-sharing')

    def test_no_case_assertions(self):
        self._test_generic_suite('app_no_case_sharing', 'suite-no-case-sharing')

    def test_attached_picture(self):
        self._test_generic_suite_partial('app_attached_image', "./detail", 'suite-attached-image')

    def test_copy_form(self):
        app = Application.new_app('domain', "Untitled Application")
        module = app.add_module(AdvancedModule.new_module('module', None))
        original_form = app.new_form(module.id, "Untitled Form", None)
        original_form.source = '<source>'

        app.copy_form(module, original_form, module, rename=True)

        form_count = 0
        for f in app.get_forms():
            form_count += 1
            if f.unique_id != original_form.unique_id:
                self.assertEqual(f.name['en'], 'Copy of {}'.format(original_form.name['en']))
        self.assertEqual(form_count, 2, 'Copy form has copied multiple times!')

    def test_copy_form_to_app(self):
        src_app = Application.new_app('domain', "Source Application")
        src_module = src_app.add_module(AdvancedModule.new_module('Source Module', None))
        original_form = src_app.new_form(src_module.id, "Untitled Form", None)
        original_form.source = '<source>'
        dst_app = Application.new_app('domain', "Destination Application")
        dst_module = dst_app.add_module(AdvancedModule.new_module('Destination Module', None))

        src_app.copy_form(src_module, original_form, dst_module, rename=True)

        self.assertEqual(len(list(src_app.get_forms())), 1, 'Form copied to the wrong app')
        dst_app_forms = list(dst_app.get_forms())
        self.assertEqual(len(dst_app_forms), 1)
        self.assertEqual(dst_app_forms[0].name['en'], 'Copy of Untitled Form')

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
        app = Application.new_app('domain', "Untitled Application")
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
        app = Application.new_app('domain', "Untitled Application")
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

    def test_usercase_id_added_update(self):
        app = Application.new_app('domain', "Untitled Application")

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'

        child_form = app.new_form(0, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'
        child_form.actions.usercase_update = UpdateCaseAction(update={'name': '/data/question1'})
        child_form.actions.usercase_update.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_usercase_id_added_preload(self):
        app = Application.new_app('domain', "Untitled Application")

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'

        child_form = app.new_form(0, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'
        child_form.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'name'})
        child_form.actions.usercase_preload.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_open_case_and_subcase(self):
        app = Application.new_app('domain', "Untitled Application")

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
        app = Application.new_app('domain', "Untitled Application")

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
        expected_suite = parse_normalize(self.get_xml('suite-fixture-graphing'), to_string=False)
        actual_suite = parse_normalize(
            Application.wrap(self.get_json('app_fixture_graphing')).create_suite(), to_string=False)

        expected_configuration_list = expected_suite.findall('detail/field/template/graph/configuration')
        actual_configuration_list = actual_suite.findall('detail/field/template/graph/configuration')

        self.assertEqual(len(expected_configuration_list), 1)
        self.assertEqual(len(actual_configuration_list), 1)

        expected_configuration = expected_configuration_list[0]
        actual_configuration = actual_configuration_list[0]

        self.assertItemsEqual(
            [tostring(text_element) for text_element in expected_configuration],
            [tostring(text_element) for text_element in actual_configuration]
        )

        expected_suite.find('detail/field/template/graph').remove(expected_configuration)
        actual_suite.find('detail/field/template/graph').remove(actual_configuration)

        self.assertXmlEqual(tostring(expected_suite), tostring(actual_suite))

    def test_printing(self):
        self._test_generic_suite('app_print_detail', 'suite-print-detail')

    def test_fixture_to_case_selection(self):
        factory = AppFactory(build_version='2.9.0')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = 'days'
        module.fixture_select.display_column = 'my_display_column'
        module.fixture_select.variable_column = 'my_variable_column'
        module.fixture_select.xpath = 'date(scheduled_date) <= date(today() + $fixture_value)'

        factory.form_requires_case(form)

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection'), factory.app.create_suite())

    def test_fixture_to_case_selection_with_form_filtering(self):
        factory = AppFactory(build_version='2.9.0')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = 'days'
        module.fixture_select.display_column = 'my_display_column'
        module.fixture_select.variable_column = 'my_variable_column'
        module.fixture_select.xpath = 'date(scheduled_date) <= date(today() + $fixture_value)'

        factory.form_requires_case(form)

        form.form_filter = "$fixture_value <= today()"

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection-with-form-filtering'), factory.app.create_suite())

    def test_fixture_to_case_selection_localization(self):
        factory = AppFactory(build_version='2.9.0')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = 'days'
        module.fixture_select.display_column = 'my_display_column'
        module.fixture_select.localize = True
        module.fixture_select.variable_column = 'my_variable_column'
        module.fixture_select.xpath = 'date(scheduled_date) <= date(today() + $fixture_value)'

        factory.form_requires_case(form)

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection-localization'), factory.app.create_suite())

    def test_fixture_to_case_selection_parent_child(self):
        factory = AppFactory(build_version='2.9.0')

        m0, m0f0 = factory.new_basic_module('parent', 'parent')
        m0.fixture_select.active = True
        m0.fixture_select.fixture_type = 'province'
        m0.fixture_select.display_column = 'display_name'
        m0.fixture_select.variable_column = 'var_name'
        m0.fixture_select.xpath = 'province = $fixture_value'

        factory.form_requires_case(m0f0)

        m1, m1f0 = factory.new_basic_module('child', 'child')
        m1.fixture_select.active = True
        m1.fixture_select.fixture_type = 'city'
        m1.fixture_select.display_column = 'display_name'
        m1.fixture_select.variable_column = 'var_name'
        m1.fixture_select.xpath = 'city = $fixture_value'

        factory.form_requires_case(m1f0, parent_case_type='parent')

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection-parent-child'), factory.app.create_suite())

    def test_case_detail_tabs(self):
        self._test_generic_suite("app_case_detail_tabs", 'suite-case-detail-tabs')

    def test_case_detail_tabs_with_nodesets(self):
        with flag_enabled('DISPLAY_CONDITION_ON_TABS'):
            self._test_generic_suite("app_case_detail_tabs_with_nodesets", 'suite-case-detail-tabs-with-nodesets')

    def test_case_detail_tabs_with_nodesets_for_sorting(self):
        app = Application.wrap(self.get_json("app_case_detail_tabs_with_nodesets"))
        app.modules[0].case_details.long.sort_nodeset_columns = True
        xml_partial = """
        <partial>
          <field>
            <header width="0">
              <text/>
            </header>
            <template width="0">
              <text>
                <xpath function="gender"/>
              </text>
            </template>
            <sort direction="ascending" order="1" type="string">
              <text>
                <xpath function="gender"/>
              </text>
            </sort>
          </field>
        </partial>"""
        self.assertXmlPartialEqual(
            xml_partial, app.create_suite(),
            './detail[@id="m0_case_long"]/detail/field/template/text/xpath[@function="gender"]/../../..')

    def test_case_detail_instance_adding(self):
        # Tests that post-processing adds instances used in calculations
        # by any of the details (short, long, inline, persistent)
        self._test_generic_suite('app_case_detail_instances', 'suite-case-detail-instances')

    def test_case_tile_suite(self):
        self._test_generic_suite("app_case_tiles", "suite-case-tiles")

    def test_case_detail_conditional_enum(self):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Unititled Module', None))
        module.case_type = 'patient'

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'Gender'},
                model='case',
                field='gender',
                format='conditional-enum',
                enum=[
                    MappingItem(key="gender = 'male' and age <= 21", value={'en': 'Boy'}),
                    MappingItem(key="gender = 'female' and age <= 21", value={'en': 'Girl'}),
                    MappingItem(key="gender = 'male' and age > 21", value={'en': 'Man'}),
                    MappingItem(key="gender = 'female' and age > 21", value={'en': 'Woman'}),
                ],
            ),
        ]

        key1_varname = hashlib.md5("gender = 'male' and age <= 21".encode('utf-8')).hexdigest()[:8]
        key2_varname = hashlib.md5("gender = 'female' and age <= 21".encode('utf-8')).hexdigest()[:8]
        key3_varname = hashlib.md5("gender = 'male' and age > 21".encode('utf-8')).hexdigest()[:8]
        key4_varname = hashlib.md5("gender = 'female' and age > 21".encode('utf-8')).hexdigest()[:8]

        icon_mapping_spec = """
        <partial>
          <template>
            <text>
              <xpath function="if(gender = 'male' and age &lt;= 21, $h{key1_varname}, if(gender = 'female' and age &lt;= 21, $h{key2_varname}, if(gender = 'male' and age &gt; 21, $h{key3_varname}, if(gender = 'female' and age &gt; 21, $h{key4_varname}, ''))))">
                <variable name="h{key4_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key4_varname}"/>
                </variable>
                <variable name="h{key2_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key2_varname}"/>
                </variable>
                <variable name="h{key3_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key3_varname}"/>
                </variable>
                <variable name="h{key1_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key1_varname}"/>
                </variable>
              </xpath>
            </text>
          </template>
        </partial>
        """.format(
            key1_varname=key1_varname,
            key2_varname=key2_varname,
            key3_varname=key3_varname,
            key4_varname=key4_varname,
        )
        # check correct suite is generated
        self.assertXmlPartialEqual(
            icon_mapping_spec,
            app.create_suite(),
            './detail[@id="m0_case_short"]/field/template'
        )
        # check app strings mapped correctly
        app_strings = commcare_translations.loads(app.create_app_strings('en'))
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key1_varname}'.format(key1_varname=key1_varname, )],
            'Boy'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key2_varname}'.format(key2_varname=key2_varname, )],
            'Girl'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key3_varname}'.format(key3_varname=key3_varname, )],
            'Man'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key4_varname}'.format(key4_varname=key4_varname, )],
            'Woman'
        )

    def test_case_detail_calculated_conditional_enum(self):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Unititled Module', None))
        module.case_type = 'patient'

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'Gender'},
                model='case',
                field="if(gender = 'male', 'boy', 'girl')",
                format='enum',
                enum=[
                    MappingItem(key="boy", value={'en': 'Boy'}),
                    MappingItem(key="girl", value={'en': 'Girl'}),
                ],
            ),
        ]

        icon_mapping_spec = """
        <partial>
          <template>
            <text>
              <xpath function="if(if(gender = 'male', 'boy', 'girl') = 'boy', $kboy, if(if(gender = 'male', 'boy', 'girl') = 'girl', $kgirl, ''))">
                <variable name="kboy">
                  <locale id="m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kboy"/>
                </variable>
                <variable name="kgirl">
                  <locale id="m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kgirl"/>
                </variable>
              </xpath>
            </text>
          </template>
        </partial>
        """
        # check correct suite is generated
        self.assertXmlPartialEqual(
            icon_mapping_spec,
            app.create_suite(),
            './detail[@id="m0_case_short"]/field/template'
        )
        # check app strings mapped correctly
        app_strings = commcare_translations.loads(app.create_app_strings('en'))
        self.assertEqual(
            app_strings["m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kboy"],
            'Boy'
        )
        self.assertEqual(
            app_strings["m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kgirl"],
            'Girl'
        )

    def test_case_detail_icon_mapping(self):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'Age range'},
                model='case',
                field='age',
                format='enum-image',
                enum=[
                    MappingItem(key='10', value={'en': 'jr://icons/10-year-old.png'}),
                    MappingItem(key='age > 50', value={'en': 'jr://icons/old-icon.png'}),
                    MappingItem(key='15%', value={'en': 'jr://icons/percent-icon.png'}),
                ],
            ),
        ]

        key1_varname = '10'
        key2_varname = hashlib.md5('age > 50'.encode('utf-8')).hexdigest()[:8]
        key3_varname = hashlib.md5('15%'.encode('utf-8')).hexdigest()[:8]

        icon_mapping_spec = """
            <partial>
              <template form="image" width="13%">
                <text>
                  <xpath function="if(age = '10', $k{key1_varname}, if(age > 50, $h{key2_varname}, if(age = '15%', $h{key3_varname}, '')))">
                    <variable name="h{key2_varname}">
                      <locale id="m0.case_short.case_age_1.enum.h{key2_varname}"/>
                    </variable>
                    <variable name="h{key3_varname}">
                      <locale id="m0.case_short.case_age_1.enum.h{key3_varname}"/>
                    </variable>
                    <variable name="k{key1_varname}">
                      <locale id="m0.case_short.case_age_1.enum.k{key1_varname}"/>
                    </variable>
                  </xpath>
                </text>
              </template>
            </partial>
        """.format(
            key1_varname=key1_varname,
            key2_varname=key2_varname,
            key3_varname=key3_varname,
        )
        # check correct suite is generated
        self.assertXmlPartialEqual(
            icon_mapping_spec,
            app.create_suite(),
            './detail/field/template[@form="image"]'
        )
        # check icons map correctly
        app_strings = commcare_translations.loads(app.create_app_strings('en'))
        self.assertEqual(
            app_strings['m0.case_short.case_age_1.enum.h{key3_varname}'.format(key3_varname=key3_varname,)],
            'jr://icons/percent-icon.png'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_age_1.enum.h{key2_varname}'.format(key2_varname=key2_varname,)],
            'jr://icons/old-icon.png'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_age_1.enum.k{key1_varname}'.format(key1_varname=key1_varname,)],
            'jr://icons/10-year-old.png'
        )

    def test_case_tile_pull_down(self):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.use_case_tiles = True
        module.case_details.short.persist_tile_on_forms = True
        module.case_details.short.pull_down_tile = True
        self._add_columns_for_case_details(module)

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        self.assertXmlPartialEqual(
            self.get_xml('case_tile_pulldown_session'),
            app.create_suite(),
            "./entry/session"
        )

    def test_inline_case_detail_from_another_module(self):
        factory = AppFactory()
        module0, form0 = factory.new_advanced_module("m0", "person")
        factory.form_requires_case(form0, "person")
        module0.case_details.short.use_case_tiles = True
        self._add_columns_for_case_details(module0)

        module1, form1 = factory.new_advanced_module("m1", "person")
        factory.form_requires_case(form1, "person")

        # not configured to use other module's persistent case tile so
        # has no detail-inline and detail-persistent attr
        self.ensure_module_session_datum_xml(factory, '', '')

        # configured to use other module's persistent case tile
        module1.case_details.short.persistent_case_tile_from_module = module0.unique_id
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')

        # configured to use other module's persistent case tile that has custom xml
        module0.case_details.short.use_case_tiles = False
        module0.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')
        module0.case_details.short.custom_xml = ''
        module0.case_details.short.use_case_tiles = True

        # configured to use pull down tile from the other module
        module1.case_details.short.pull_down_tile = True
        self.ensure_module_session_datum_xml(factory, 'detail-inline="m0_case_long"',
                                             'detail-persistent="m0_case_short"')

        # set to use persistent case tile of its own as well but it would still
        # persists case tiles and detail inline from another module
        module1.case_details.short.use_case_tiles = True
        module1.case_details.short.persist_tile_on_forms = True
        self._add_columns_for_case_details(module1)
        self.ensure_module_session_datum_xml(factory, 'detail-inline="m0_case_long"',
                                             'detail-persistent="m0_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and has own persistent case tile as well
        # So now detail inline from its own details
        module0.case_details.short.use_case_tiles = False
        self.ensure_module_session_datum_xml(factory, 'detail-inline="m1_case_long"',
                                             'detail-persistent="m1_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and does not have its own persistent case tile as well
        module1.case_details.short.use_case_tiles = False
        self.ensure_module_session_datum_xml(factory, '', '')

    def test_persistent_case_tiles_from_another_module(self):
        factory = AppFactory()
        module0, form0 = factory.new_advanced_module("m0", "person")
        factory.form_requires_case(form0, "person")
        module0.case_details.short.use_case_tiles = True
        self._add_columns_for_case_details(module0)

        module1, form1 = factory.new_advanced_module("m1", "person")
        factory.form_requires_case(form1, "person")

        # not configured to use other module's persistent case tile so
        # has no detail-persistent attr
        self.ensure_module_session_datum_xml(factory, '', '')

        # configured to use other module's persistent case tile
        module1.case_details.short.persistent_case_tile_from_module = module0.unique_id
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')

        # configured to use other module's persistent case tile that has custom xml
        module0.case_details.short.use_case_tiles = False
        module0.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')
        module0.case_details.short.custom_xml = ''
        module0.case_details.short.use_case_tiles = True

        # set to use persistent case tile of its own as well but it would still
        # persists case tiles from another module
        module1.case_details.short.use_case_tiles = True
        module1.case_details.short.persist_tile_on_forms = True
        self._add_columns_for_case_details(module1)
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and has own persistent case tile as well
        module0.case_details.short.use_case_tiles = False
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m1_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and does not have its own persistent case tile as well
        module1.case_details.short.use_case_tiles = False
        self.ensure_module_session_datum_xml(factory, '', '')

    def test_persistent_case_tiles_in_advanced_forms(self):
        """
        Test that the detail-persistent attributes is set correctly when persistent
        case tiles are used on advanced forms.
        """
        factory = AppFactory()
        module, form = factory.new_advanced_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        module.case_details.short.persist_tile_on_forms = True
        suite = factory.app.create_suite()

        # The relevant check is really that detail-persistent="m0_case_short"
        # but assertXmlPartialEqual xpath implementation doesn't currently
        # support selecting attributes
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_case_short"
                    detail-select="m0_case_short"
                    id="case_id_load_person_0"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            "entry/session/datum"
        )

    def test_persistent_case_tiles_in_advanced_module_case_lists(self):
        """
        Test that the detail-persistent attributes is set correctly when persistent
        case tiles are used on advanced module case lists
        """
        factory = AppFactory()
        module, form = factory.new_advanced_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_list.show = True
        module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        module.case_details.short.persist_tile_on_forms = True
        suite = factory.app.create_suite()

        # The relevant check is really that detail-persistent="m0_case_short"
        # but assertXmlPartialEqual xpath implementation doesn't currently
        # support selecting attributes
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_case_short"
                    detail-select="m0_case_short"
                    id="case_id_case_person"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            'entry/command[@id="m0-case-list"]/../session/datum',
        )

    def test_persistent_case_name_in_forms(self):
        """
        Test that the detail-persistent attributes are set correctly when the
        module is configured to persist the case name at the top of the form.
        Also confirm that the appropriate <detail> element is added to the suite.
        """
        factory = AppFactory()
        module, form = factory.new_basic_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_details.short.persist_case_context = True
        suite = factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <detail id="m0_persistent_case_context">
                    <title>
                        <text/>
                    </title>
                    <field>
                        <style font-size="large" horz-align="center">
                            <grid grid-height="1" grid-width="12" grid-x="0" grid-y="0"/>
                        </style>
                        <header>
                            <text/>
                        </header>
                        <template>
                            <text>
                                <xpath function="case_name"/>
                            </text>
                        </template>
                    </field>
                </detail>
            </partial>
            """,
            suite,
            "detail[@id='m0_persistent_case_context']"
        )

        # The attribute we care about here is detail-persistent="m0_persistent_case_context"
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_persistent_case_context"
                    detail-select="m0_case_short"
                    id="case_id"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            "entry/session/datum"
        )

    def test_persistent_case_name_when_tiles_enabled(self):
        """
        Confirm that the persistent case name context is not added when case tiles
        are configured to persist in forms
        """
        factory = AppFactory()
        module, form = factory.new_advanced_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        module.case_details.short.use_case_tiles = True
        module.case_details.short.persist_tile_on_forms = True
        module.case_details.short.persist_case_context = True
        suite = factory.app.create_suite()

        self.assertXmlDoesNotHaveXpath(suite, "detail[@id='m0_persistent_case_context']")
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_case_short"
                    detail-select="m0_case_short"
                    id="case_id_load_person_0"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            "entry/session/datum"
        )

    def test_subcase_repeat_mixed(self):
        app = Application.new_app(None, "Untitled Application")
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
        from corehq.apps.userreports.tests.utils import get_sample_report_config

        app = Application.new_app('domain', "Untitled Application")

        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.unique_id = 'report_module'
        report = get_sample_report_config()
        report._id = 'd3ff18cd83adf4550b35db8d391f6008'

        report_app_config = ReportAppConfig(
            report_id=report._id,
            header={'en': 'CommBugz'},
            uuid='ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i',
            xpath_description='"report description"',
            use_xpath_description=True,
            complete_graph_configs={
                chart.chart_id: GraphConfiguration(
                    graph_type="bar",
                    series=[GraphSeries() for c in chart.y_axis_columns],
                )
                for chart in report.charts
            },
        )
        report_app_config._report = report
        report_module.report_configs = [report_app_config]
        report_module._loaded = True
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_menu'),
            app.create_suite(),
            "./menu",
        )

        app.multimedia_map = {
            "jr://file/commcare/image/module0_en.png": HQMediaMapItem(
                multimedia_id='bb4472b4b3c702f81c0b208357eb22f8',
                media_type='CommCareImage',
                unique_id='fe06454697634053cdb75fd9705ac7e6',
            ),
        }
        report_module.media_image = {
            'en': 'jr://file/commcare/image/module0_en.png',
        }
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_menu_multimedia'),
            app.create_suite(),
            "./menu",
        )

        self.assertXmlPartialEqual(
            self.get_xml('reports_module_select_detail'),
            app.create_suite(),
            "./detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.select']",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_summary_detail_use_xpath_description'),
            app.create_suite(),
            "./detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.summary']",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_data_detail'),
            app.create_suite(),
            "./detail/detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.data']",
        )

        report_app_config.show_data_table = False
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_summary_detail_hide_data_table'),
            app.create_suite(),
            "./detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.summary']",
        )
        report_app_config.show_data_table = True

        self.assertXmlPartialEqual(
            self.get_xml('reports_module_data_entry'),
            app.create_suite(),
            "./entry",
        )
        self.assertIn(
            'reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i=CommBugz',
            app.create_app_strings('default'),
        )

        report_app_config.use_xpath_description = False
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_summary_detail_use_localized_description'),
            app.create_suite(),
            "./detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.summary']",
        )

        # Tuple mapping translation formats to the expected output of each
        translation_formats = [
            ({
                'एक': {
                    'en': 'one',
                    'es': 'uno',
                },
                '2': {
                    'en': 'two',
                    'es': 'dos\'',
                    'hin': 'दो',
                },
            }, 'reports_module_data_detail-translated'),
            ({
                'एक': 'one',
                '2': 'two',
            }, 'reports_module_data_detail-translated-simple'),
            ({
                'एक': {
                    'en': 'one',
                    'es': 'uno',
                },
                '2': 'two',
            }, 'reports_module_data_detail-translated-mixed'),
        ]
        for translation_format, expected_output in translation_formats:
            report_app_config._report.columns[0]['transform'] = {
                'type': 'translation',
                'translations': translation_format,
            }
            report_app_config._report = ReportConfiguration.wrap(report_app_config._report._doc)
            self.assertXmlPartialEqual(
                self.get_xml(expected_output),
                app.create_suite(),
                "./detail/detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.data']",
            )

    def test_circular_parent_case_ref(self):
        factory = AppFactory()
        m0, m0f0 = factory.new_basic_module('m0', 'case1')
        m1, m1f0 = factory.new_basic_module('m1', 'case2')
        factory.form_requires_case(m0f0, 'case1', parent_case_type='case2')
        factory.form_requires_case(m1f0, 'case2', parent_case_type='case1')

        with self.assertRaises(SuiteValidationError):
            factory.app.create_suite()

    def test_custom_assertions(self):
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

    def test_custom_variables(self):
        factory = AppFactory()
        module, form = factory.new_basic_module('m0', 'case1')
        factory.form_requires_case(form, 'case')
        short_custom_variables = "<variable function='true()' /><foo function='bar'/>"
        long_custom_variables = (
            '<bar function="true()" />'
            '<baz function="instance(\'locations\')/locations/location[0]"/>'
        )
        module.case_details.short.custom_variables = short_custom_variables
        module.case_details.long.custom_variables = long_custom_variables
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <variables>
                    {short_variables}
                </variables>
                <variables>
                    {long_variables}
                </variables>
            </partial>
            """.format(short_variables=short_custom_variables, long_variables=long_custom_variables),
            suite,
            "detail/variables"
        )
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id="casedb" src="jr://instance/casedb"/>
                <instance id="locations" src="jr://fixture/locations"/>
            </partial>
            """.format(short_variables=short_custom_variables, long_variables=long_custom_variables),
            suite,
            "entry[1]/instance"
        )


class InstanceTests(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        super(InstanceTests, self).setUp()
        self.factory = AppFactory(include_xmlns=True)
        self.module, self.form = self.factory.new_basic_module('m0', 'case1')

    def test_custom_instances(self):
        instance_id = "foo"
        instance_path = "jr://foo/bar"
        self.form.custom_instances = [CustomInstance(instance_id=instance_id, instance_path=instance_path)]
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='{}' src='{}' />
            </partial>
            """.format(instance_id, instance_path),
            self.factory.app.create_suite(),
            "entry/instance"
        )

    def test_duplicate_custom_instances(self):
        self.factory.form_requires_case(self.form)
        instance_id = "casedb"
        instance_path = "jr://casedb/bar"
        # Use form_filter to add instances
        self.form.form_filter = "count(instance('casedb')/casedb/case[@case_id='123']) > 0"
        self.form.custom_instances = [CustomInstance(instance_id=instance_id, instance_path=instance_path)]
        with self.assertRaises(DuplicateInstanceIdError):
            self.factory.app.create_suite()

    def test_duplicate_regular_instances(self):
        """Make sure instances aren't getting added multiple times if they are referenced multiple times
        """
        self.factory.form_requires_case(self.form)
        self.form.form_filter = "instance('casedb') instance('casedb') instance('locations') instance('locations')"
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='casedb' src='jr://instance/casedb' />
                <instance id='locations' src='jr://fixture/locations' />
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )

    def test_location_instances(self):
        self.form.form_filter = "instance('locations')/locations/"
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='locations' src='jr://fixture/locations' />
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )

    @mock.patch.object(LocationFixtureConfiguration, 'for_domain')
    def test_location_instance_during_migration(self, sync_patch):
        # tests for expectations during migration from hierarchical to flat location fixture
        # Domains with HIERARCHICAL_LOCATION_FIXTURE enabled and with sync_flat_fixture set to False
        # should have hierarchical jr://fixture/commtrack:locations fixture format
        # All other cases to have flat jr://fixture/locations fixture format
        self.form.form_filter = "instance('locations')/locations/"
        configuration_mock_obj = mock.MagicMock()
        sync_patch.return_value = configuration_mock_obj

        hierarchical_fixture_format_xml = """
            <partial>
                <instance id='locations' src='jr://fixture/commtrack:locations' />
            </partial>
        """

        flat_fixture_format_xml = """
            <partial>
                <instance id='locations' src='jr://fixture/locations' />
            </partial>
        """

        configuration_mock_obj.sync_flat_fixture = True  # default value
        # Domains migrating to flat location fixture, will have FF enabled and should successfully be able to
        # switch between hierarchical and flat fixture
        with flag_enabled('HIERARCHICAL_LOCATION_FIXTURE'):
            configuration_mock_obj.sync_hierarchical_fixture = True  # default value
            self.assertXmlPartialEqual(flat_fixture_format_xml,
                                       self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_hierarchical_fixture = False
            self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_flat_fixture = False
            self.assertXmlPartialEqual(hierarchical_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_hierarchical_fixture = True
            self.assertXmlPartialEqual(hierarchical_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

        # To ensure for new domains or domains adding locations now come on flat fixture
        configuration_mock_obj.sync_hierarchical_fixture = True  # default value
        self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

        # This should not happen ideally since the conf can not be set without having HIERARCHICAL_LOCATION_FIXTURE
        # enabled. Considering that a domain has sync hierarchical fixture set to False without the FF
        # HIERARCHICAL_LOCATION_FIXTURE. In such case the domain stays on flat fixture format
        configuration_mock_obj.sync_hierarchical_fixture = False
        self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

    def test_unicode_lookup_table_instance(self):
        self.form.form_filter = "instance('item-list:província')/província/"
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='item-list:província' src='jr://fixture/item-list:província' />
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )
