import json
import uuid

from mock import patch

from django.test import TestCase
from casexml.apps.case.signals import case_post_save

from corehq.apps.userreports import tasks
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import post_case_blocks
from corehq.apps.userreports.reports.view import ConfigurableReport, \
    UCR_EXPORT_TO_EXCEL_ROW_LIMIT
from corehq.sql_db.connections import Session
from corehq.util.context_managers import drop_connected_signals


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
        ).as_xml()
        with drop_connected_signals(case_post_save):
            post_case_blocks([case_block], {'domain': cls.domain})
        return CommCareCase.get(id)

    @classmethod
    def _delete_everything(cls):
        delete_all_cases()
        for config in DataSourceConfiguration.all():
            config.delete()
        delete_all_report_configs()


class ConfigurableReportViewTest(ConfigurableReportTestMixin, TestCase):

    @classmethod
    def _build_report_and_view(cls):

        # Create Cases
        cls._new_case({'fruit': 'apple', 'num1': 4, 'num2': 6}).save()

        # Create report
        data_source_config = DataSourceConfiguration(
            domain=cls.domain,
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
                "property_value": cls.case_type,
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
        tasks.rebuild_indicators(data_source_config._id)

        report_config = ReportConfiguration(
            domain=cls.domain,
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
            ],
        )
        report_config.save()

        view = ConfigurableReport()
        view._domain = cls.domain
        view._lang = "en"
        view._report_config_id = report_config._id

        return report_config, view

    @classmethod
    def tearDown(cls):
        cls._delete_everything()
        # todo: understand why this is necessary. the view call uses the session and the
        # signal doesn't fire to kill it.
        Session.remove()

    @classmethod
    def setUp(cls):
        cls._delete_everything()

    def test_export_table(self):
        """
        Test the output of ConfigurableReport.export_table()
        """
        report, view = self._build_report_and_view()

        expected = [
            [
                u'foo',
                [
                    [u'report_column_display_fruit', u'report_column_display_percent'],
                    [u'apple', '150%']
                ]
            ]
        ]
        self.assertEqual(view.export_table, expected)

    def test_export_to_excel_size_under_limit(self):
        report, view = self._build_report_and_view()

        response = json.loads(view.export_size_check_response.content)
        self.assertEqual(response['export_allowed'], True)

    def test_export_to_excel_size_over_limit(self):
        report, view = self._build_report_and_view()

        with patch(
            'corehq.apps.userreports.reports.data_source.ConfigurableReportDataSource.get_total_records',
            return_value=UCR_EXPORT_TO_EXCEL_ROW_LIMIT + 1
        ):
            response = json.loads(view.export_size_check_response.content)
        self.assertEqual(response['export_allowed'], False)

        self.assertEqual(view.export_response.status_code, 400)

    def test_paginated_build_table(self):
        """
        Simulate building a report where chunking occurs
        """

        with patch('corehq.apps.userreports.tasks.ID_CHUNK_SIZE', 1):
            report, view = self._build_report_and_view()

        expected = [
            [
                u'foo',
                [
                    [u'report_column_display_fruit', u'report_column_display_percent'],
                    [u'apple', '150%']
                ]
            ]
        ]
        self.assertEqual(view.export_table, expected)
