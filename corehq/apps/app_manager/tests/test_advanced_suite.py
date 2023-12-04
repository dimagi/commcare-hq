from django.test import SimpleTestCase

from corehq.apps.app_manager.const import (
    AUTO_SELECT_CASE,
    AUTO_SELECT_FIXTURE,
    AUTO_SELECT_RAW,
    AUTO_SELECT_USER,
    AUTO_SELECT_USERCASE,
)
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    ArbitraryDatum,
    AutoSelectCase,
    CaseSearch,
    CaseSearchProperty,
    LoadCaseFromFixture,
    LoadUpdateAction,
    Module,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)
from corehq.util.test_utils import flag_enabled


@patch_get_xform_resource_overrides()
class AdvancedSuiteTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_advanced_suite(self, *args):
        self._test_generic_suite('suite-advanced')

    def test_advanced_suite_multi_select(self, *args):
        app = Application.wrap(self.get_json("suite-advanced"))
        app.modules[1].case_details.short.multi_select = True
        self.assertXmlEqual(self.get_xml("suite-advanced"), app.create_suite())

    def test_advanced_suite_details(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        clinic_module_id = app.get_module(0).unique_id
        other_module_id = app.get_module(1).unique_id
        app.get_module(1).get_form(0).actions.load_update_cases[0].details_module = clinic_module_id
        app.get_module(1).get_form(1).actions.load_update_cases[0].details_module = other_module_id
        self.assertXmlEqual(self.get_xml('suite-advanced-details'), app.create_suite())

    def test_advanced_suite_parent_child_custom_ref(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        form = app.get_module(1).get_form(2)
        form.actions.load_update_cases[1].case_index.reference_id = 'custom-parent-ref'
        self.assertXmlPartialEqual(self.get_xml('custom-parent-ref'), app.create_suite(), "./entry[4]")

    def test_advanced_suite_case_list_filter(self, *args):
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

    def test_advanced_suite_auto_select_case_mobile(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).auto_select_case = True
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-case-mobile'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_user(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_USER,
            value_key='case_id'
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-user'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_fixture(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_FIXTURE,
            value_source='table_tag',
            value_key='field_name'
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-fixture'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_raw(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_RAW,
            value_key=("some xpath expression "
                       "containing instance('casedb') "
                       "and instance('commcaresession')")
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-raw'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_case(self, *args):
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

    def test_advanced_suite_auto_select_usercase(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases[0].auto_select = AutoSelectCase(
            mode=AUTO_SELECT_USERCASE
        )
        self.assertXmlPartialEqual(self.get_xml('suite-advanced-autoselect-usercase'), app.create_suite(),
                                   './entry[2]')

    def test_advanced_suite_auto_select_with_filter(self, *args):
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
            <command id="m1-f0" relevant="instance('casedb')/casedb/""" +\
            """case[@case_id=instance('commcaresession')/session/data/case_id_case_clinic]/edd = '123'"/>
            <command id="m1-f1"/>
            <command id="m1-f2"/>
            <command id="m1-case-list"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(menu, suite, "./menu[@id='m1']")

    def test_advanced_suite_load_case_from_fixture(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_tag="adherence",
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('item-list:table_tag')/calendar/year/month"
                                "/day[@date > 735992 and @date < 736000]",
                fixture_tag="selected_date",
                fixture_variable="./@date",
                case_property="adherence_event_date",
                auto_select=True,
            )
        ))
        suite = app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('load_case_from_fixture_session'), suite, './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_case_from_fixture_instance'), suite, './entry[2]/instance')

    def test_advanced_suite_load_case_from_fixture_with_arbitrary_datum(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_tag="adherence",
            case_type="clinic",
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('item-list:table_tag')/calendar/year/month/"
                                "day[@date > 735992 and @date < 736000]",
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

    def test_advanced_suite_arbitrary_datum(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.get_module(1).get_form(0).arbitrary_datums = [
            ArbitraryDatum(datum_id='extra_id1', datum_function='extra_function1()'),
            ArbitraryDatum(datum_id='extra_id2', datum_function='extra_function2()')
        ]
        suite = app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <session>
                    <datum detail-confirm="m1_case_long" detail-select="m1_case_short" id="case_id_case_clinic"
                           nodeset="instance('casedb')/casedb/case[@case_type='clinic'][@status='open']"
                           value="./@case_id"/>
                    <datum id="extra_id1" function="extra_function1()" />
                    <datum id="extra_id2" function="extra_function2()" />
                </session>
            </partial>
            """,
            suite,
            './entry[2]/session'
        )

    @flag_enabled('MOBILE_UCR')
    def test_advanced_suite_load_case_from_fixture_with_report_fixture(self, *args):
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
        self.assertXmlPartialEqual(self.get_xml('load_case_from_report_fixture_session'), suite,
                                   './entry[2]/session')
        self.assertXmlPartialEqual(self.get_xml('load_case_from_report_fixture_instance'), suite,
                                   './entry[2]/instance')

    def test_advanced_suite_load_from_fixture(self, *args):
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

    def test_advanced_suite_load_from_fixture_auto_select(self, *args):
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

    def test_tiered_select_with_advanced_module_as_parent(self, *args):
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

    def test_parent_select_null_relationship(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        parent_module = app.add_module(Module.new_module('parent', None))
        parent_module.case_type = 'parent'
        parent_module.unique_id = 'id_parent_module'

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'
        child_module.parent_select.active = True

        # make child module point to advanced module as parent
        child_module.parent_select.module_id = parent_module.unique_id
        child_module.parent_select.relationship = None

        child_form = app.new_form(1, "Untitled Form", None)
        child_form.xmlns = 'http://id_m0-f0'
        child_form.requires = 'case'

        self.assertXmlPartialEqual(
            self.get_xml('advanced_module_parent_null_relationship'),
            app.create_suite(),
            "./entry[1]"
        )

    def test_parent_select_null_relationship_same_case_type(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        parent_module = app.add_module(Module.new_module('parent', None))
        parent_module.case_type = 'person'
        parent_module.unique_id = 'id_parent_module'

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'person'
        child_module.parent_select.active = True

        # make child module point to advanced module as parent
        child_module.parent_select.module_id = parent_module.unique_id
        child_module.parent_select.relationship = None

        child_form = app.new_form(1, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'

        self.assertXmlPartialEqual(
            self.get_xml('parent_null_relationship_same_type'),
            app.create_suite(),
            "./entry[1]"
        )

    def test_tiered_select_with_advanced_module_as_parent_with_filters(self, *args):
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

    def test_advanced_module_remote_request(self, *args):
        factory = AppFactory(domain='domain', build_version='2.53.0')
        factory.app._id = "123"
        m0, f0 = factory.new_advanced_module("search", "patient")
        factory.form_requires_case(f0)

        m0.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ]
        )
        m0.assign_references()
        suite = factory.app.create_suite()
        expected = """
        <partial>
          <remote-request>
            <post url="http://localhost:8000/a/domain/phone/claim-case/"
                relevant="count(instance('casedb')/casedb/""" +\
            """case[@case_id=instance('commcaresession')/session/data/search_case_id]) = 0">
              <data key="case_id" ref="instance('commcaresession')/session/data/search_case_id"/>
            </post>
            <command id="search_command.m0">
              <display>
                <text>
                  <locale id="case_search.m0"/>
                </text>
              </display>
            </command>
            <instance id="casedb" src="jr://instance/casedb"/>
            <instance id="commcaresession" src="jr://instance/session"/>
            <instance id="results" src="jr://instance/remote/results"/>
            <session>
              <query url="http://localhost:8000/a/domain/phone/search/123/"
                storage-instance="results" template="case" default_search="false" dynamic_search="false">
                <title>
                    <text>
                        <locale id="case_search.m0.inputs"/>
                    </text>
                </title>
                <data key="case_type" ref="'patient'"/>
                <prompt key="name">
                  <display>
                    <text>
                      <locale id="search_property.m0.name"/>
                    </text>
                  </display>
                </prompt>
              </query>
              <datum id="search_case_id"
                nodeset="instance('results')/results/case[@case_type='patient'][not(commcare_is_related_case=true())]"
                value="./@case_id" detail-select="m0_search_short" detail-confirm="m0_search_long"/>
            </session>
            <stack>
              <push>
                <rewind value="instance('commcaresession')/session/data/search_case_id"/>
              </push>
            </stack>
          </remote-request>
        </partial>"""
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]")
