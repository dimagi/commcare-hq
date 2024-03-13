from django.test import SimpleTestCase

from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchAgainLabel,
    CaseSearchLabel,
    CaseSearchProperty,
    GraphConfiguration,
    GraphSeries,
    ReportAppConfig,
    ReportModule,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
    case_search_sync_cases_on_form_entry_enabled_for_domain
)
from corehq.apps.hqmedia.models import HQMediaMapItem
from corehq.apps.userreports.models import ReportConfiguration


@patch_get_xform_resource_overrides()
class SuiteTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_normal_suite(self, *args):
        self._test_generic_suite('app', 'normal-suite')

    def test_tiered_select(self, *args):
        self._test_generic_suite('tiered-select', 'tiered-select')

    def test_3_tiered_select(self, *args):
        self._test_generic_suite('tiered-select-3', 'tiered-select-3')

    def test_case_search_action(self):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.modules[0].search_config = CaseSearch(
            search_label=CaseSearchLabel(
                label={'en': 'Get them'},
                media_image={'en': "jr://file/commcare/image/1.png"},
                media_audio={'en': "jr://file/commcare/image/2.mp3"}
            ),
            search_again_label=CaseSearchAgainLabel(
                label={'en': 'Get them'},
                media_audio={'en': "jr://file/commcare/image/2.mp3"}
            ),
            properties=[CaseSearchProperty(name='name', label={'en': 'Name'})],
        )
        # wrap to have assign_references called
        app = Application.wrap(app.to_json())

        # test for legacy action node for older versions
        self.assertXmlPartialEqual(
            self.get_xml('case-search-with-action'),
            app.create_suite(),
            "./detail[@id='m0_case_short']/action"
        )
        self.assertXmlPartialEqual(
            self.get_xml('case-search-again-with-action'),
            app.create_suite(),
            "./detail[@id='m0_search_short']/action"
        )

        # test for localized action node for apps with CC version > 2.21
        app.build_spec.version = '2.21.0'
        self.assertXmlPartialEqual(
            self.get_xml('case-search-with-localized-action'),
            app.create_suite(),
            "./detail[@id='m0_case_short']/action"
        )
        self.assertXmlPartialEqual(
            self.get_xml('case-search-again-with-localized-action'),
            app.create_suite(),
            "./detail[@id='m0_search_short']/action"
        )

    def test_callcenter_suite(self, *args):
        self._test_generic_suite('call-center')

    def test_attached_picture(self, *args):
        self._test_generic_suite_partial('app_attached_image', "./detail", 'suite-attached-image')

    def test_owner_name(self, *args):
        self._test_generic_suite('owner-name')

    def test_printing(self, *args):
        self._test_generic_suite('app_print_detail', 'suite-print-detail')

    def test_report_module(self, *args):
        from corehq.apps.userreports.tests.utils import get_sample_report_config

        app = Application.new_app('domain', "Untitled Application")

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
        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.unique_id = 'report_module'
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
        report_module.get_details.reset_cache(report_module)
        actual_suite = app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_menu_multimedia'),
            actual_suite,
            "./menu",
        )

        self.assertXmlPartialEqual(
            self.get_xml('reports_module_select_detail'),
            actual_suite,
            "./detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.select']",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_summary_detail_use_xpath_description'),
            actual_suite,
            "./detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.summary']",
        )
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_data_detail'),
            actual_suite,
            "./detail/detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.data']",
        )

        report_app_config.show_data_table = False
        report_module.get_details.reset_cache(report_module)
        self.assertXmlPartialEqual(
            self.get_xml('reports_module_summary_detail_hide_data_table'),
            app.create_suite(),
            "./detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.summary']",
        )

        report_app_config.show_data_table = True
        report_module.get_details.reset_cache(report_module)
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
        report_module.get_details.reset_cache(report_module)
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
            report_module.get_details.reset_cache(report_module)
            self.assertXmlPartialEqual(
                self.get_xml(expected_output),
                app.create_suite(),
                "./detail/detail[@id='reports.ip1bjs8xtaejnhfrbzj2r6v1fi6hia4i.data']",
            )

    def test_circular_parent_case_ref(self, *args):
        factory = AppFactory()
        m0, m0f0 = factory.new_basic_module('m0', 'case1')
        m1, m1f0 = factory.new_basic_module('m1', 'case2')
        factory.form_requires_case(m0f0, 'case1', parent_case_type='case2')
        factory.form_requires_case(m1f0, 'case2', parent_case_type='case1')

        with self.assertRaises(SuiteValidationError):
            factory.app.create_suite()

    def test_custom_variables(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('m0', 'case1')
        factory.form_requires_case(form, 'case')
        short_custom_variables = "<variable function='true()' /><foo function='bar'/>"
        short_custom_variables_dict = {"variable": "true()", "foo": "bar"}
        long_custom_variables = (
            '<bar function="true()" />'
            '<baz function="instance(\'locations\')/locations/location[0]"/>'
        )
        long_custom_variables_dict = {"bar": "true()", "baz": "instance(\'locations\')/locations/location[0]"}
        module.case_details.short.custom_variables_dict = short_custom_variables_dict
        module.case_details.long.custom_variables_dict = long_custom_variables_dict
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
            """,
            suite,
            "entry[1]/instance"
        )

    def test_sync_cases_on_form_entry_disabled(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('m0', 'case1')
        form.requires = 'case'

        module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
        )
        module.assign_references()
        self.assertXmlDoesNotHaveXpath(factory.app.create_suite(), "./entry/post")

    @case_search_sync_cases_on_form_entry_enabled_for_domain()
    def test_sync_cases_on_form_entry_enabled(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('m0', 'case1')
        form.requires = 'case'

        module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
        )
        module.assign_references()
        self.assertXmlHasXpath(factory.app.create_suite(), "./entry/post")
