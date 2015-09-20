import uuid

from django.test import TestCase

from corehq.apps.userreports import tasks
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from corehq.apps.userreports.reports.view import ConfigurableReport
from corehq.db import Session


class ConfigurableReportViewTest(TestCase):
    domain = 'my_domain'
    case_type = 'my_case_type'

    @classmethod
    def _new_case(cls, properties):
        id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=id,
            case_type=cls.case_type,
            version=V2,
            update=properties,
        ).as_xml()
        post_case_blocks([case_block], {'domain': cls.domain})
        return CommCareCase.get(id)

    @classmethod
    def _build_report(cls):

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
        return report_config

    @classmethod
    def _delete_everything(cls):
        delete_all_cases()
        for config in DataSourceConfiguration.all():
            config.delete()
        for config in ReportConfiguration.all():
            config.delete()

    @classmethod
    def tearDownClass(cls):
        cls._delete_everything()
        # todo: understand why this is necessary. the view call uses the session and the
        # signal doesn't fire to kill it.
        Session.remove()

    @classmethod
    def setUpClass(cls):
        cls._delete_everything()
        cls.report = cls._build_report()

    def test_export_table(self):
        """
        Test the output of ConfigurableReport.export_table()
        """
        # Create a configurable report
        view = ConfigurableReport()
        view.domain = self.domain
        view.lang = "en"
        view.report_config_id = self.report._id

        self.assertEqual(
            view.export_table,
            [
                [
                    u'foo',
                    [
                        [u'report_column_display_fruit', u'report_column_display_percent'],
                        [u'apple', '150%']
                    ]
                ]
            ]
        )
