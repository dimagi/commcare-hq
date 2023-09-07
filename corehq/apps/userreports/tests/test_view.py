import uuid
from unittest.mock import patch

from django.http import HttpRequest
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.userreports import tasks
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.view import ConfigurableReportView
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.signals import sql_case_post_save
from corehq.sql_db.connections import Session
from corehq.util.context_managers import drop_connected_signals
from corehq.util.test_utils import flag_enabled


class ConfigurableReportTestMixin(object):
    domain = "TEST_DOMAIN"
    case_type = "CASE_TYPE"

    @classmethod
    def _new_case(cls, properties):
        id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=id,
            case_type=cls.case_type,
            update=properties,
        ).as_text()
        with drop_connected_signals(sql_case_post_save):
            submit_case_blocks(case_block, domain=cls.domain)
        return CommCareCase.objects.get_case(id, cls.domain)

    @classmethod
    def _delete_everything(cls):
        delete_all_cases()
        for config in DataSourceConfiguration.all():
            config.delete()
        delete_all_report_configs()


class ConfigurableReportViewTest(ConfigurableReportTestMixin, TestCase):

    def _build_report_and_view(self, request=HttpRequest()):
        # Create report
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id="woop_woop",
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": self.case_type,
            },
            configured_indicators=[
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'fruit'
                    },
                    "column_id": 'indicator_col_id_fruit',
                    "display_name": 'indicator_display_name_fruit',
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'num1'
                    },
                    "column_id": 'indicator_col_id_num1',
                    "datatype": "integer"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'num2'
                    },
                    "column_id": 'indicator_col_id_num2',
                    "datatype": "integer"
                },
            ],
        )
        data_source_config.validate()
        data_source_config.save()
        self.addCleanup(data_source_config.delete)
        tasks.rebuild_indicators(data_source_config._id)
        adapter = get_indicator_adapter(data_source_config)
        self.addCleanup(adapter.drop_table)

        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config._id,
            title='foo',
            aggregation_columns=['doc_id'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_fruit",
                    "field": 'indicator_col_id_fruit',
                    'column_id': 'report_column_col_id_fruit',
                    'aggregation': 'simple'
                },
                {
                    "type": "percent",
                    "display": "report_column_display_percent",
                    'column_id': 'report_column_col_id_percent',
                    'format': 'percent',
                    "denominator": {
                        "type": "field",
                        "aggregation": "sum",
                        "field": "indicator_col_id_num1",
                        "column_id": "report_column_col_id_percent_num1"
                    },
                    "numerator": {
                        "type": "field",
                        "aggregation": "sum",
                        "field": "indicator_col_id_num2",
                        "column_id": "report_column_col_id_percent_num2"
                    }
                },
                {
                    "type": "expanded",
                    "display": "report_column_display_expanded_num1",
                    "field": 'indicator_col_id_num1',
                    'column_id': 'report_column_col_id_expanded_num1',
                }
            ],
            configured_charts=[
                {
                    "type": 'pie',
                    "value_column": 'count',
                    "aggregation_column": 'fruit',
                    "title": 'Fruits'
                },
                {
                    "type": 'multibar',
                    "title": 'Fruit Properties',
                    "x_axis_column": 'fruit',
                    "y_axis_columns": [
                        {"column_id": "report_column_col_id_expanded_num1", "display": "Num1 values"}
                    ]
                },

            ]
        )
        report_config.save()
        self.addCleanup(report_config.delete)

        view = ConfigurableReportView(request=request)
        view._domain = self.domain
        view._lang = "en"
        view._report_config_id = report_config._id

        return report_config, view

    @classmethod
    def tearDownClass(cls):
        # todo: understand why this is necessary. the view call uses the session and the
        # signal doesn't fire to kill it.
        Session.remove()
        super().tearDownClass()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cases = []
        cls.cases.append(cls._new_case({'fruit': 'apple', 'num1': 4, 'num2': 6}))
        cls.cases.append(cls._new_case({'fruit': 'mango', 'num1': 7, 'num2': 4}))
        cls.cases.append(cls._new_case({'fruit': 'unknown', 'num1': 1, 'num2': 0}))

    def test_export_table(self):
        """
        Test the output of ConfigurableReportView.export_table()
        """
        report, view = self._build_report_and_view()
        expected = [
            [
                'foo',
                [
                    [
                        'report_column_display_fruit',
                        'report_column_display_percent',
                        'report_column_display_expanded_num1-1',
                        'report_column_display_expanded_num1-4',
                        'report_column_display_expanded_num1-7',
                    ],
                    ['apple', '150%', 0, 1, 0],
                    ['mango', '57%', 0, 0, 1],
                    ['unknown', '0%', 1, 0, 0]
                ]
            ]
        ]
        self.assertEqual(view.export_table, expected)

    def test_report_preview_data(self):
        """
        Test the output of ConfigurableReportView.export_table()
        """
        report, view = self._build_report_and_view()

        actual = ConfigurableReportView.report_preview_data(report.domain, report)
        expected = {
            "table": [
                [
                    'report_column_display_fruit',
                    'report_column_display_percent',
                    'report_column_display_expanded_num1-1',
                    'report_column_display_expanded_num1-4',
                    'report_column_display_expanded_num1-7',
                ],
                ['apple', '150%', 0, 1, 0],
                ['mango', '57%', 0, 0, 1],
                ['unknown', '0%', 1, 0, 0]
            ],
            "map_config": report.map_config,
            "chart_configs": report.charts,
            "aaData": [
                {
                    "report_column_col_id_fruit": "apple",
                    "report_column_col_id_percent": "150%",
                    'report_column_col_id_expanded_num1-0': 0,
                    'report_column_col_id_expanded_num1-1': 1,
                    'report_column_col_id_expanded_num1-2': 0,
                },
                {
                    'report_column_col_id_fruit': 'mango',
                    'report_column_col_id_percent': '57%',
                    'report_column_col_id_expanded_num1-0': 0,
                    'report_column_col_id_expanded_num1-1': 0,
                    'report_column_col_id_expanded_num1-2': 1,
                },
                {
                    'report_column_col_id_fruit': 'unknown',
                    'report_column_col_id_percent': '0%',
                    'report_column_col_id_expanded_num1-0': 1,
                    'report_column_col_id_expanded_num1-1': 0,
                    'report_column_col_id_expanded_num1-2': 0,
                }
            ]
        }
        self.assertEqual(actual, expected)

    def test_report_preview_data_with_expanded_columns(self):
        report, view = self._build_report_and_view()
        multibar_chart = report.charts[1].to_json()
        self.assertEqual(multibar_chart['type'], 'multibar')
        self.assertEqual(
            multibar_chart['y_axis_columns'],
            [
                {
                    'column_id': 'report_column_col_id_expanded_num1',
                    'display': 'Num1 values'
                }
            ]
        )

        with flag_enabled('SUPPORT_EXPANDED_COLUMN_IN_REPORTS'):
            report, view = self._build_report_and_view()
            multibar_chart = report.charts[1].to_json()
            self.assertEqual(multibar_chart['type'], 'multibar')
            self.assertEqual(
                multibar_chart['y_axis_columns'],
                [
                    {
                        'column_id': 'report_column_col_id_expanded_num1-0',
                        'display': 'report_column_display_expanded_num1-1'
                    },
                    {
                        'column_id': 'report_column_col_id_expanded_num1-1',
                        'display': 'report_column_display_expanded_num1-4'
                    },
                    {
                        'column_id': 'report_column_col_id_expanded_num1-2',
                        'display': 'report_column_display_expanded_num1-7'
                    },
                ]
            )

            # just test that preview works
            self.test_report_preview_data()

    def test_report_charts(self):
        report, view = self._build_report_and_view()

        preview_data = ConfigurableReportView.report_preview_data(report.domain, report)
        preview_data_pie_chart = preview_data['chart_configs'][0]
        self.assertEqual(preview_data_pie_chart.type, 'pie')
        self.assertEqual(preview_data_pie_chart.title, 'Fruits')
        self.assertEqual(preview_data_pie_chart.value_column, 'count')
        self.assertEqual(preview_data_pie_chart.aggregation_column, 'fruit')

        preview_data_multibar_chart = preview_data['chart_configs'][1]
        self.assertEqual(preview_data_multibar_chart.type, 'multibar')
        self.assertEqual(preview_data_multibar_chart.title, 'Fruit Properties')
        self.assertEqual(preview_data_multibar_chart.title, 'Fruit Properties')
        self.assertEqual(preview_data_multibar_chart.x_axis_column, 'fruit')
        self.assertEqual(
            preview_data_multibar_chart.y_axis_columns[0].column_id,
            'report_column_col_id_expanded_num1'
        )
        self.assertEqual(
            preview_data_multibar_chart.y_axis_columns[0].display,
            'Num1 values'
        )

    @flag_enabled('SUPPORT_EXPANDED_COLUMN_IN_REPORTS')
    def test_report_charts_with_expanded_columns(self):
        report, view = self._build_report_and_view()

        preview_data = ConfigurableReportView.report_preview_data(report.domain, report)
        multibar_chart = preview_data['chart_configs'][1].to_json()
        self.assertEqual(multibar_chart['type'], 'multibar')
        self.assertEqual(
            multibar_chart['y_axis_columns'],
            [
                {
                    'column_id': 'report_column_col_id_expanded_num1-0',
                    'display': 'report_column_display_expanded_num1-1'
                },
                {
                    'column_id': 'report_column_col_id_expanded_num1-1',
                    'display': 'report_column_display_expanded_num1-4'
                },
                {
                    'column_id': 'report_column_col_id_expanded_num1-2',
                    'display': 'report_column_display_expanded_num1-7'
                },
            ]
        )

    def test_paginated_build_table(self):
        """
        Simulate building a report where chunking occurs
        """

        with patch('corehq.apps.userreports.tasks.ID_CHUNK_SIZE', 1):
            report, view = self._build_report_and_view()
        expected = [
            [
                'foo',
                [
                    [
                        'report_column_display_fruit',
                        'report_column_display_percent',
                        'report_column_display_expanded_num1-1',
                        'report_column_display_expanded_num1-4',
                        'report_column_display_expanded_num1-7',
                    ],
                    ['apple', '150%', 0, 1, 0],
                    ['mango', '57%', 0, 0, 1],
                    ['unknown', '0%', 1, 0, 0]
                ]
            ]
        ]
        self.assertEqual(view.export_table, expected)

    def test_redirect_custom_report(self):
        report, view = self._build_report_and_view()
        request = HttpRequest()
        self.assertFalse(view.should_redirect_to_paywall(request))

    def test_redirect_report_builder(self):
        report, view = self._build_report_and_view()
        report.report_meta.created_by_builder = True
        report.save()
        request = HttpRequest()
        self.assertTrue(view.should_redirect_to_paywall(request))

    def test_can_edit_report(self):
        """
        Test whether ConfigurableReportView.page_context allows report editing
        """
        domain = Domain(name='test_domain', is_active=True)
        domain.save()
        self.addCleanup(domain.delete)

        def create_view(can_edit_reports):
            rolename = 'edit_role' if can_edit_reports else 'view_role'
            username = 'editor' if can_edit_reports else 'viewer'
            toggles.USER_CONFIGURABLE_REPORTS.set(username, True, toggles.NAMESPACE_USER)

            # user_role should be deleted along with the domain.
            user_role = UserRole.create(
                domain=domain.name,
                name=rolename,
                permissions=HqPermissions(edit_commcare_users=True,
                                          view_commcare_users=True,
                                          edit_groups=True,
                                          view_groups=True,
                                          edit_locations=True,
                                          view_locations=True,
                                          access_all_locations=False,
                                          edit_data=True,
                                          edit_reports=can_edit_reports,
                                          view_reports=True
                                          )
            )

            web_user = WebUser.create(domain.name, username, '***', None, None)
            web_user.set_role(domain.name, user_role.get_qualified_id())
            web_user.current_domain = domain.name
            web_user.save()
            self.addCleanup(web_user.delete, domain.name, deleted_by=None)

            request = HttpRequest()
            request.can_access_all_locations = True
            request.user = web_user.get_django_user()
            request.couch_user = web_user
            request.session = {}
            _, view = self._build_report_and_view(request=request)
            return view

        cannot_edit_view = create_view(False)
        self.assertEqual(cannot_edit_view.page_context['can_edit_report'], False)

        can_edit_view = create_view(True)
        self.assertEqual(can_edit_view.page_context['can_edit_report'], True)
