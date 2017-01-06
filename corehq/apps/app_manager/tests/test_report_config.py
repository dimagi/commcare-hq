import os
from xml.etree import ElementTree
from django.test import SimpleTestCase, TestCase
import mock
from casexml.apps.phone.tests.utils import create_restore_user
from corehq.apps.app_manager.fixtures import report_fixture_generator
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users

from corehq.apps.app_manager.models import ReportAppConfig, Application, ReportModule, \
    ReportGraphConfig, MobileSelectFilter
from corehq.apps.app_manager.tests.mocks.mobile_ucr import mock_report_configurations, \
    mock_report_configuration_get, mock_report_data
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import ReportConfiguration, ReportMeta
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceProvider
from corehq.apps.userreports.reports.filters.specs import DynamicChoiceListFilterSpec, ChoiceListFilterSpec, \
    FilterChoice
from corehq.apps.userreports.reports.specs import FieldColumn, MultibarChartSpec, \
    GraphDisplayColumn
from corehq.apps.userreports.tests.utils import mock_datasource_config, mock_sql_backend
from corehq.toggles import MOBILE_UCR, NAMESPACE_DOMAIN
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache


class ReportAppConfigTest(SimpleTestCase):

    def test_new_uuid(self):
        report_app_config = ReportAppConfig(report_id='report_id')
        self.assertTrue(report_app_config.uuid)
        self.assertIsInstance(report_app_config.uuid, basestring)

    def test_different_uuids(self):
        report_app_config_1 = ReportAppConfig(report_id='report_id')
        report_app_config_2 = ReportAppConfig(report_id='report_id')
        self.assertNotEqual(report_app_config_1.uuid, report_app_config_2.uuid)

    def test_existing_uuid(self):
        existing_uuid = 'existing_uuid'
        self.assertEqual(
            existing_uuid,
            ReportAppConfig.wrap({
                "report_id": "report_id",
                "uuid": existing_uuid,
            }).uuid
        )


MAKE_REPORT_CONFIG = lambda domain, report_id: ReportConfiguration(
    _id=report_id,
    title="Entry Report",
    aggregation_columns=["color_94ec39e6"],
    config_id="516c494736e95b023cc7845b557de0f5",
    domain=domain,
    report_meta=ReportMeta(builder_report_type="chart", created_by_builder=True),
    columns=[
        FieldColumn(type='field', aggregation="simple", column_id="color_94ec39e6", display="color", field="color_94ec39e6").to_json(),
    ],
    configured_charts=[
        MultibarChartSpec(type='multibar', chart_id="7451243209119342931", x_axis_column="color_94ec39e6",
                          y_axis_columns=[GraphDisplayColumn(column_id="count", display="count")]).to_json()
    ],
    filters=[
        DynamicChoiceListFilterSpec(
            type='dynamic_choice_list',
            display="owner name",
            field="computed_owner_name_40cc88a0",
            slug="computed_owner_name_40cc88a0_1"
        ).to_json(),
        ChoiceListFilterSpec(
            type='choice_list',
            display="fav color",
            field="fav_fruit_abc123",
            slug="fav_fruit_abc123_1",
            choices=[
                FilterChoice(value='a', display='apple'),
                FilterChoice(value='b', display='banana'),
                FilterChoice(value='c', display='clementine'),
            ]
        ).to_json()
    ],
)


class ReportFiltersSuiteTest(TestCase, TestXmlMixin):
    file_path = 'data', 'mobile_ucr'
    root = os.path.dirname(__file__)

    @staticmethod
    def make_report_config(domain, report_id):
        class MockChoiceProvider(ChoiceProvider):

            def query(self, query_context):
                pass

            def get_choices_for_known_values(self, values):
                _map = {'cory': 'Cory Zue', 'ctsims': 'Clayton Sims', 'daniel': 'Daniel Roberts'}
                return [Choice(value, _map.get(value, value)) for value in values]

        report_configuration = MAKE_REPORT_CONFIG(domain, report_id)
        ui_filter = report_configuration.get_ui_filter('computed_owner_name_40cc88a0_1')
        ui_filter.choice_provider = MockChoiceProvider(None, None)
        return report_configuration

    @classmethod
    def setUpClass(cls):
        delete_all_users()
        cls.report_id = '7b97e8b53d00d43ca126b10093215a9d'
        cls.report_config_uuid = 'a98c812873986df34fd1b4ceb45e6164ae9cc664'
        cls.domain = 'report-filter-test-domain'
        cls.user = create_restore_user(
            domain=cls.domain,
            username='ralph',
        )
        update_toggle_cache(MOBILE_UCR.slug, cls.domain, True, NAMESPACE_DOMAIN)

        report_configuration = cls.make_report_config(cls.domain, cls.report_id)
        cls.report_configs_by_id = {
            cls.report_id: report_configuration
        }
        cls.app = Application.new_app(cls.domain, "Report Filter Test App")
        module = cls.app.add_module(ReportModule.new_module("Report Module", 'en'))
        module.report_configs.append(
            ReportAppConfig(
                report_id=cls.report_id,
                header={},
                description="",
                graph_configs={
                    '7451243209119342931': ReportGraphConfig(
                        series_configs={'count': {}}
                    )
                },
                filters={
                    'computed_owner_name_40cc88a0_1': MobileSelectFilter(),
                    'fav_fruit_abc123_1': MobileSelectFilter()
                },
                uuid=cls.report_config_uuid,
            )
        )
        with mock_report_configurations(cls.report_configs_by_id):
            cls.suite = cls.app.create_suite()
        cls.data = [
            {'color_94ec39e6': 'red', 'count': 2, 'computed_owner_name_40cc88a0': 'cory', 'fav_fruit_abc123': 'c'},
            {'color_94ec39e6': 'black', 'count': 1, 'computed_owner_name_40cc88a0': 'ctsims', 'fav_fruit_abc123': 'b'},
            {'color_94ec39e6': 'red', 'count': 3, 'computed_owner_name_40cc88a0': 'daniel', 'fav_fruit_abc123': 'b'},
        ]
        with mock_report_data(cls.data):
            with mock_report_configuration_get(cls.report_configs_by_id):
                with mock.patch('corehq.apps.app_manager.fixtures.mobile_ucr.get_apps_in_domain',
                                lambda domain, include_remote: [cls.app]):
                    with mock_sql_backend():
                        with mock_datasource_config():
                            fixture, = report_fixture_generator(cls.user, '2.0')
        cls.fixture = ElementTree.tostring(fixture)

    @classmethod
    def tearDownClass(cls):
        clear_toggle_cache(MOBILE_UCR.slug, cls.domain, NAMESPACE_DOMAIN)

    def test_filter_entry(self):
        self.assertXmlPartialEqual("""
        <partial>
          <entry>
            <command id="reports.a98c812873986df34fd1b4ceb45e6164ae9cc664">
              <text>
                <locale id="cchq.reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.name"/>
              </text>
            </command>
            <instance id="commcaresession" src="jr://instance/session"/>
            <instance id="reports" src="jr://fixture/commcare:reports"/>
            <session>
              <datum id="report_filter_a98c812873986df34fd1b4ceb45e6164ae9cc664_fav_fruit_abc123_1" nodeset="instance('reports')/reports/report[@id='a98c812873986df34fd1b4ceb45e6164ae9cc664']/filters/filter[@field='fav_fruit_abc123_1']/option" value="./@value" detail-select="reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.filter.fav_fruit_abc123_1" />
              <datum id="report_filter_a98c812873986df34fd1b4ceb45e6164ae9cc664_computed_owner_name_40cc88a0_1" nodeset="instance('reports')/reports/report[@id='a98c812873986df34fd1b4ceb45e6164ae9cc664']/filters/filter[@field='computed_owner_name_40cc88a0_1']/option" value="./@value" detail-select="reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.filter.computed_owner_name_40cc88a0_1"/>
              <datum id="report_id_a98c812873986df34fd1b4ceb45e6164ae9cc664" nodeset="instance('reports')/reports/report[@id='a98c812873986df34fd1b4ceb45e6164ae9cc664']" value="./@id" detail-select="reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.select" detail-confirm="reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.summary" autoselect="true"/>
            </session>
          </entry>
        </partial>
        """, self.suite, "entry")

    def test_filter_detail(self):
        self.assertXmlPartialEqual("""
        <partial>
          <detail id="reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.filter.computed_owner_name_40cc88a0_1">
            <title>
              <text>owner name</text>
            </title>
            <field>
              <header>
                <text>owner name</text>
              </header>
              <template>
                <text>
                  <xpath function="."/>
                </text>
              </template>
            </field>
          </detail>
        </partial>
        """, self.suite, "detail[@id='reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.filter.computed_owner_name_40cc88a0_1']")

    def test_data_detail(self):
        self.assertXmlPartialEqual("""
        <partial>
          <detail nodeset="rows/row[column[@id='fav_fruit_abc123']=instance('commcaresession')/session/data/report_filter_a98c812873986df34fd1b4ceb45e6164ae9cc664_fav_fruit_abc123_1][column[@id='computed_owner_name_40cc88a0']=instance('commcaresession')/session/data/report_filter_a98c812873986df34fd1b4ceb45e6164ae9cc664_computed_owner_name_40cc88a0_1]" id="reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.data">
            <title>
              <text>
                <locale id="cchq.report_data_table"/>
              </text>
            </title>
            <field>
              <header>
                <text>
                  <locale id="cchq.reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.headers.color_94ec39e6"/>
                </text>
              </header>
              <template>
                <text>
                  <xpath function="column[@id='color_94ec39e6']"/>
                </text>
              </template>
            </field>
          </detail>
        </partial>
        """, self.suite, "detail/detail[@id='reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.data']")

    def test_graph(self):
        self.assertXmlPartialEqual("""
        <partial>
          <template form="graph">
            <graph type="bar">
              <series nodeset="instance('reports')/reports/report[@id='a98c812873986df34fd1b4ceb45e6164ae9cc664']/rows/row[@is_total_row='False'][column[@id='fav_fruit_abc123']=instance('commcaresession')/session/data/report_filter_a98c812873986df34fd1b4ceb45e6164ae9cc664_fav_fruit_abc123_1][column[@id='computed_owner_name_40cc88a0']=instance('commcaresession')/session/data/report_filter_a98c812873986df34fd1b4ceb45e6164ae9cc664_computed_owner_name_40cc88a0_1]">
                <configuration/>
                <x function="column[@id='color_94ec39e6']"/>
                <y function="column[@id='count']"/>
              </series>
              <configuration/>
            </graph>
          </template>
        </partial>
        """, self.suite, "detail[@id='reports.a98c812873986df34fd1b4ceb45e6164ae9cc664.summary']/detail/field/template[@form='graph']")

    def test_fixture_rows(self):
        self.assertXmlPartialEqual("""
        <partial>
          <rows>
            <row index="0" is_total_row="False">
              <column id="color_94ec39e6">red</column>
              <column id="computed_owner_name_40cc88a0">cory</column>
              <column id="count">2</column>
              <column id="fav_fruit_abc123">c</column>
            </row>
            <row index="1" is_total_row="False">
              <column id="color_94ec39e6">black</column>
              <column id="computed_owner_name_40cc88a0">ctsims</column>
              <column id="count">1</column>
              <column id="fav_fruit_abc123">b</column>
            </row>
            <row index="2" is_total_row="False">
              <column id="color_94ec39e6">red</column>
              <column id="computed_owner_name_40cc88a0">daniel</column>
              <column id="count">3</column>
              <column id="fav_fruit_abc123">b</column>
            </row>
          </rows>
        </partial>
        """, self.fixture, "reports/report/rows")

    def test_fixture_filters(self):
        self.assertXmlPartialEqual("""
        <partial>
          <filters>
            <filter field="fav_fruit_abc123_1">
              <option value="b">banana</option>
              <option value="c">clementine</option>
            </filter>
            <filter field="computed_owner_name_40cc88a0_1">
              <option value="ctsims">Clayton Sims</option>
              <option value="cory">Cory Zue</option>
              <option value="daniel">Daniel Roberts</option>
            </filter>
          </filters>
        </partial>
        """, self.fixture, "reports/report/filters")
