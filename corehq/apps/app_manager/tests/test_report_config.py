from __future__ import absolute_import, unicode_literals

import os
from collections import OrderedDict
from xml.etree import cElementTree as ElementTree

from django.test import SimpleTestCase, TestCase

import mock
import six

from casexml.apps.phone.tests.utils import (
    call_fixture_generator,
    create_restore_user,
)

from corehq.apps.app_manager.const import MOBILE_UCR_VERSION_2
from corehq.apps.app_manager.fixtures import report_fixture_generator
from corehq.apps.app_manager.models import (
    Application,
    GraphConfiguration,
    GraphSeries,
    MobileSelectFilter,
    Module,
    ReportAppConfig,
    ReportModule,
    _filter_by_user_id,
    _get_auto_filter_function,
)
from corehq.apps.app_manager.suite_xml.features.mobile_ucr import get_uuids_by_instance_id
from corehq.apps.app_manager.tests.mocks.mobile_ucr import (
    mock_report_configuration_get,
    mock_report_configurations,
    mock_report_data,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import ReportConfiguration, ReportMeta
from corehq.apps.userreports.reports.filters.choice_providers import (
    ChoiceProvider,
)
from corehq.apps.userreports.reports.filters.specs import (
    ChoiceListFilterSpec,
    DynamicChoiceListFilterSpec,
    FilterChoice,
)
from corehq.apps.userreports.reports.specs import (
    FieldColumn,
    GraphDisplayColumn,
    MultibarChartSpec,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_report_config,
    mock_datasource_config,
)
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.toggles import MOBILE_UCR, NAMESPACE_DOMAIN
from corehq.util.test_utils import flag_enabled


class ReportAppConfigTest(SimpleTestCase):

    def test_new_uuid(self):
        report_app_config = ReportAppConfig(report_id='report_id')
        self.assertTrue(report_app_config.uuid)
        self.assertIsInstance(report_app_config.uuid, six.text_type)

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


def MAKE_REPORT_CONFIG(domain, report_id, columns=None):
    columns = columns or [
        FieldColumn(
            type='field',
            aggregation="simple",
            column_id="color_94ec39e6",
            display="color",
            field="color_94ec39e6"
        ).to_json(),
    ]
    return ReportConfiguration(
        _id=report_id,
        title="Entry Report",
        aggregation_columns=["color_94ec39e6"],
        config_id="516c494736e95b023cc7845b557de0f5",
        domain=domain,
        report_meta=ReportMeta(builder_report_type="chart", created_by_builder=True),
        columns=columns,
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

            def get_choices_for_known_values(self, values, user):
                _map = {'cory': 'Cory Zue', 'ctsims': 'Clayton Sims', 'daniel': 'Daniel Roberts'}
                return [Choice(value, _map.get(value, value)) for value in values]

        report_configuration = MAKE_REPORT_CONFIG(domain, report_id)
        ui_filter = report_configuration.get_ui_filter('computed_owner_name_40cc88a0_1')
        ui_filter.choice_provider = MockChoiceProvider(None, None)
        return report_configuration

    @classmethod
    def setUpClass(cls):
        super(ReportFiltersSuiteTest, cls).setUpClass()
        delete_all_users()
        cls.report_id = '7b97e8b53d00d43ca126b10093215a9d'
        cls.report_config_mobile_id = 'a98c812873986df34fd1b4ceb45e6164ae9cc664'
        cls.domain = 'report-filter-test-domain'
        create_domain(cls.domain)
        cls.user = create_restore_user(
            domain=cls.domain,
            username='ralph',
        )
        MOBILE_UCR.set(cls.domain, True, NAMESPACE_DOMAIN)

        report_configuration = cls.make_report_config(cls.domain, cls.report_id)

        # also make a report with a hidden column
        cls.hidden_column_report_id = 'bd2a43018ad9463682165c1bc16347ac'
        cls.hidden_column_mobile_id = '45152061d8dc4d2a8d987a0568abe1ae'
        report_configuration_with_hidden_column = MAKE_REPORT_CONFIG(
            cls.domain,
            cls.hidden_column_report_id,
            columns=[
                FieldColumn(
                    type='field',
                    aggregation="simple",
                    column_id="color_94ec39e6",
                    display="color",
                    field="color_94ec39e6"
                ).to_json(),
                FieldColumn(
                    type='field',
                    aggregation="simple",
                    column_id="hidden_color_94ec39e6",
                    display="color",
                    field="color_94ec39e6",
                    visible=False,
                ).to_json(),
            ]
        )
        cls.report_configs_by_id = {
            cls.report_id: report_configuration,
            cls.hidden_column_report_id: report_configuration_with_hidden_column
        }
        cls.app = Application.new_app(cls.domain, "Report Filter Test App")
        module = cls.app.add_module(ReportModule.new_module("Report Module", 'en'))
        module.report_configs.append(
            ReportAppConfig(
                report_id=cls.report_id,
                header={},
                description="",
                complete_graph_configs={
                    '7451243209119342931': GraphConfiguration(
                        graph_type="bar",
                        series=[GraphSeries(
                            config={},
                            locale_specific_config={},
                            data_path="",
                            x_function="",
                            y_function="",
                        )],
                    )
                },
                filters=OrderedDict([
                    ('fav_fruit_abc123_1', MobileSelectFilter()),
                    ('computed_owner_name_40cc88a0_1', MobileSelectFilter()),
                ]),
                uuid=cls.report_config_mobile_id,
            )
        )
        module.report_configs.append(
            ReportAppConfig(
                report_id=cls.hidden_column_report_id,
                header={},
                description="",
                complete_graph_configs={},
                filters={},
                uuid=cls.hidden_column_mobile_id,
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
                    with mock_datasource_config():
                        fixture, = call_fixture_generator(report_fixture_generator, cls.user)
        cls.fixture = ElementTree.tostring(fixture)

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
          <entry>
            <command id="reports.45152061d8dc4d2a8d987a0568abe1ae">
              <text>
                <locale id="cchq.reports.45152061d8dc4d2a8d987a0568abe1ae.name"/>
              </text>
            </command>
            <instance id="reports" src="jr://fixture/commcare:reports"/>
            <session>
              <datum autoselect="true" detail-confirm="reports.45152061d8dc4d2a8d987a0568abe1ae.summary" detail-select="reports.45152061d8dc4d2a8d987a0568abe1ae.select" id="report_id_45152061d8dc4d2a8d987a0568abe1ae" nodeset="instance('reports')/reports/report[@id='45152061d8dc4d2a8d987a0568abe1ae']" value="./@id"/>
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
        """, self.fixture, "reports/report[@id='a98c812873986df34fd1b4ceb45e6164ae9cc664']/rows")

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
        """, self.fixture, "reports/report[@id='a98c812873986df34fd1b4ceb45e6164ae9cc664']/filters")

    def test_hidden_columns_data_detail(self):
        self.assertXmlPartialEqual("""
        <partial>
          <detail id="reports.45152061d8dc4d2a8d987a0568abe1ae.data" nodeset="rows/row">
            <title>
              <text>
                <locale id="cchq.report_data_table"/>
              </text>
            </title>
            <field>
              <header>
                <text>
                  <locale id="cchq.reports.45152061d8dc4d2a8d987a0568abe1ae.headers.color_94ec39e6"/>
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
        """, self.suite, "detail/detail[@id='reports.45152061d8dc4d2a8d987a0568abe1ae.data']")


class TestReportAutoFilters(SimpleTestCase):

    def test_get_filter_function(self):
        fn = _get_auto_filter_function('user_id')
        self.assertEqual(fn, _filter_by_user_id)


@flag_enabled('MOBILE_UCR')
class TestReportConfigInstances(TestCase, TestXmlMixin):
    file_path = ('data',)
    domain = 'test_report_config_instances'

    def tearDown(self):
        get_uuids_by_instance_id.clear(self.domain)

    def test_autogenerate_instance_declaration(self):
        app = self._make_app("Untitled Application")
        report_app_config = self._add_report(app, "my_report")
        form = self._add_form_with_report_reference(app, report_app_config)

        expected_declaration = ("""<instance id="commcare-reports:{}" src="jr://fixture/commcare-reports:{}"/>"""
                                .format(report_app_config.report_slug, report_app_config.uuid))
        self.assertIn(expected_declaration, self._render_form(app, form))

    def _make_app(self, app_name):
        app = Application.new_app(self.domain, app_name)
        app.mobile_ucr_restore_version = MOBILE_UCR_VERSION_2
        app.save()
        self.addCleanup(app.delete)
        return app

    def _add_report(self, app, report_slug):
        report = get_sample_report_config()
        report.domain = self.domain
        report.save()
        self.addCleanup(report.delete)
        report_app_config = ReportAppConfig(
            report_id=report._id,
            report_slug=report_slug,
        )
        report_app_config._report = report

        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.report_configs = [report_app_config]
        app.save()
        return report_app_config

    def _add_form_with_report_reference(self, app, report_app_config):
        other_module = app.add_module(Module.new_module('m0', None))
        form = other_module.new_form('f0', None)
        report_reference = "instance('commcare-reports:{}')/rows/row[0]/@index".format(report_app_config.report_slug)
        form.source = self.get_xml('very_simple_form').decode('utf-8')
        form.source = form.source.replace(
            """<bind nodeset="/data/question1" type="xsd:string"/>""",
            """<bind nodeset="/data/question1" type="xsd:string" calculate="{}"/>""".format(report_reference),
        )
        app.save()
        return form

    def _render_form(self, app, form):
        with mock.patch('corehq.apps.app_manager.suite_xml.features.mobile_ucr.get_apps_in_domain', lambda d: [app]):
            return form.render_xform().decode('utf-8')
