from django.test import TestCase

from corehq.apps.userreports.exceptions import UserReportsError
from corehq.apps.userreports.models import DataSourceConfiguration, \
    ReportConfiguration
from corehq.apps.userreports.reports.view import ConfigurableReport
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.tests import ConfigurableReportTestMixin


class TestReportAggregation(ConfigurableReportTestMixin, TestCase):
    """
    Integration tests for configurable report aggregation
    """
    dependent_apps = [
        'corehq.apps.tzmigration',
        'casexml.apps.case',
        'casexml.apps.phone',
        'corehq.couchapps',
        'corehq.form_processor',
        'couchforms',
    ]

    @classmethod
    def _create_data(cls):
        """
        Populate the database with some cases
        """
        for row in [
            {"first_name": "Alan", "number": 4},
            {"first_name": "Alan", "number": 2},
            {"first_name": "Ada", "number": 3},
        ]:
            cls._new_case(row).save()

    @classmethod
    def _create_data_source(cls):
        cls.data_source_config = DataSourceConfiguration(
            domain=cls.domain,
            display_name=cls.domain,
            referenced_doc_type='CommCareCase',
            table_id="foo",
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
                        "property_name": 'first_name'
                    },
                    "column_id": 'indicator_col_id_first_name',
                    "display_name": 'indicator_display_name_first_name',
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'number'
                    },
                    "column_id": 'indicator_col_id_number',
                    "datatype": "integer"
                },
            ],
        )
        cls.data_source_config.validate()
        cls.data_source_config.save()
        rebuild_indicators(cls.data_source_config._id)

    @classmethod
    def setUpClass(cls):
        cls._create_data()
        cls._create_data_source()

    def _create_report(self, aggregation_columns, columns):
        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=self.data_source_config._id,
            title='foo',
            aggregation_columns=aggregation_columns,
            columns=columns,
        )
        report_config.save()
        return report_config

    def _create_view(self, report_config):
        view = ConfigurableReport()
        view._domain = self.domain
        view._lang = "en"
        view._report_config_id = report_config._id
        return view

    def test_aggregation_by_column_not_in_report(self):
        """
        Confirm that aggregation works when the aggregated by column does
        not appear in the report columns.
        """
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[{
                "type": "field",
                "display": "report_column_display_number",
                "field": 'indicator_col_id_number',
                'column_id': 'report_column_col_id_number',
                'aggregation': 'sum'
            }]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [u'report_column_display_number'],
                    [3],
                    [6]
                ]
            ]]
        )

    def test_aggregation_by_column_in_report(self):
        """
        Confirm that aggregation works when the aggregated by column appears in
        the report columns (and no column_id is specified for the report column).
        """
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'aggregation': 'simple'
                },
                {
                    "type": "field",
                    "display": "report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'sum'
                }
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [u'report_column_display_first_name', u'report_column_display_number'],
                    [u'Ada', 3],
                    [u'Alan', 6]
                ]
            ]]
        )

    def test_aggregation_by_indicator_in_percent_column(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_number'],
            columns=[
                {
                    "type": "percent",
                    "display": "report_column_display_percent",
                    "denominator": {
                        "type": "field",
                        "field": 'indicator_col_id_number',
                        "aggregation": "sum",
                        "column_id": "report_column_numerator"
                    },
                    "numerator": {
                        "type": "field",
                        "field": 'indicator_col_id_number',
                        "aggregation": "sum",
                    },
                    "column_id": "report_column_percent"
                }
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [u'report_column_display_percent'],
                    [u'100%'],
                    [u'100%'],
                    [u'100%'],
                ]
            ]]
        )

    def test_aggregation_by_column_with_new_id(self):
        """
        Confirm that aggregation works when the aggregated by column appears in
        the report columns with a column_id that differs from the corresponding
        indicator column_id
        """
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'column_id': 'report_column_col_id_first_name',
                    'aggregation': 'simple'
                },
                {
                    "type": "field",
                    "display": "report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'sum'
                }
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [u'report_column_display_first_name', u'report_column_display_number'],
                    [u'Ada', 3],
                    [u'Alan', 6]
                ]
            ]]
        )

    def test_sort_expression(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[{
                "type": "field",
                "display": "indicator_col_id_first_name",
                "field": 'indicator_col_id_first_name',
                'column_id': 'indicator_col_id_first_name',
                'aggregation': 'simple'
            }]
        )

        default_sorted_view = self._create_view(report_config)
        self.assertEqual(
            default_sorted_view.export_table,
            [[
                u'foo',
                [
                    [u'indicator_col_id_first_name'],
                    [u'Ada'],
                    [u'Alan']
                ]
            ]]
        )

        report_config.sort_expression = [{
            'field': 'indicator_col_id_first_name',
            'order': 'ASC',
        }]
        report_config.save()
        ascending_sorted_view = self._create_view(report_config)
        self.assertEqual(
            ascending_sorted_view.export_table,
            [[
                u'foo',
                [
                    [u'indicator_col_id_first_name'],
                    [u'Ada'],
                    [u'Alan']
                ]
            ]]
        )

        report_config.sort_expression = [{
            'field': 'indicator_col_id_first_name',
            'order': 'DESC',
        }]
        report_config.save()
        descending_sorted_view = self._create_view(report_config)
        self.assertEqual(
            descending_sorted_view.export_table,
            [[
                u'foo',
                [
                    [u'indicator_col_id_first_name'],
                    [u'Alan'],
                    [u'Ada']
                ]
            ]]
        )

    def test_total_row(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'column_id': 'report_column_col_id_first_name',
                    'aggregation': 'simple',
                },
                {
                    "type": "field",
                    "display": "sum_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'sum_report_column_display_number',
                    'aggregation': 'sum',
                    'calculate_total': True,
                },
                {
                    "type": "field",
                    "display": "min_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'min_report_column_display_number',
                    'aggregation': 'min',
                    'calculate_total': False,
                },
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [
                        u'report_column_display_first_name',
                        u'sum_report_column_display_number',
                        u'min_report_column_display_number',
                    ],
                    [u'Ada', 3, 3],
                    [u'Alan', 6, 2],
                    [u'Total', 9, ''],
                ]
            ]]
        )

    def test_no_total_row(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'column_id': 'report_column_col_id_first_name',
                    'aggregation': 'simple',
                },
                {
                    "type": "field",
                    "display": "sum_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'sum_report_column_display_number',
                    'aggregation': 'sum',
                    'calculate_total': False,
                },
                {
                    "type": "field",
                    "display": "min_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'min_report_column_display_number',
                    'aggregation': 'min',
                    'calculate_total': False,
                },
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [
                        u'report_column_display_first_name',
                        u'sum_report_column_display_number',
                        u'min_report_column_display_number',
                    ],
                    [u'Ada', 3, 3],
                    [u'Alan', 6, 2],
                ]
            ]]
        )

    def test_total_row_first_column_value(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[
                {
                    "type": "field",
                    "display": "sum_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'sum_report_column_display_number',
                    'aggregation': 'sum',
                    'calculate_total': True,
                },
                {
                    "type": "field",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'column_id': 'report_column_col_id_first_name',
                    'aggregation': 'simple',
                },
                {
                    "type": "field",
                    "display": "min_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'min_report_column_display_number',
                    'aggregation': 'min',
                    'calculate_total': False,
                },
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [
                        u'sum_report_column_display_number',
                        u'report_column_display_first_name',
                        u'min_report_column_display_number',
                    ],
                    [3, u'Ada', 3],
                    [6, u'Alan', 2],
                    [9, '', ''],
                ]
            ]]
        )

    def test_totaling_noninteger_column(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'column_id': 'report_column_col_id_first_name',
                    'aggregation': 'simple',
                    'calculate_total': True,
                },
            ]
        )
        view = self._create_view(report_config)

        with self.assertRaises(UserReportsError):
            view.export_table

    def test_total_row_with_expanded_column(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_first_name'],
            columns=[
                {
                    "type": "field",
                    "display": "sum_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'sum_report_column_display_number',
                    'aggregation': 'sum',
                    'calculate_total': True,
                },
                {
                    "type": "expanded",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'column_id': 'report_column_col_id_first_name',
                    'calculate_total': True,
                },
                {
                    "type": "field",
                    "display": "min_report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'min_report_column_display_number',
                    'aggregation': 'min',
                    'calculate_total': True,
                },
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                u'foo',
                [
                    [
                        u'sum_report_column_display_number',
                        u'report_column_display_first_name-Ada',
                        u'report_column_display_first_name-Alan',
                        u'min_report_column_display_number',
                    ],
                    [3, 1, 0, 3],
                    [6, 0, 2, 2],
                    [9, 1, 2, 5],
                ]
            ]]
        )
