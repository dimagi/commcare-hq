from __future__ import absolute_import
from __future__ import unicode_literals
from django.http import HttpRequest
from django.test import TestCase

from corehq.apps.userreports.exceptions import UserReportsError
from corehq.apps.userreports.models import DataSourceConfiguration, \
    ReportConfiguration
from corehq.apps.userreports.reports.view import ConfigurableReportView
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.tests.test_view import ConfigurableReportTestMixin
from corehq.apps.userreports.util import get_indicator_adapter


class TestReportAggregationSQL(ConfigurableReportTestMixin, TestCase):
    """
    Integration tests for configurable report aggregation
    """

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
        cls.data_source = DataSourceConfiguration(
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
        cls.data_source.validate()
        cls.data_source.save()
        rebuild_indicators(cls.data_source._id)
        cls.adapter = get_indicator_adapter(cls.data_source)

    @classmethod
    def setUpClass(cls):
        super(TestReportAggregationSQL, cls).setUpClass()
        cls._create_data()
        cls._create_data_source()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.drop_table()
        cls._delete_everything()
        super(TestReportAggregationSQL, cls).tearDownClass()

    def _create_report(self, aggregation_columns, columns, sort_expression=None):
        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=self.data_source._id,
            title='foo',
            aggregation_columns=aggregation_columns,
            columns=columns,
        )
        if sort_expression:
            report_config.sort_expression = sort_expression
        report_config.save()
        return report_config

    def _create_view(self, report_config):
        view = ConfigurableReportView(request=HttpRequest())
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
                'foo',
                [
                    ['report_column_display_number'],
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
                'foo',
                [
                    ['report_column_display_first_name', 'report_column_display_number'],
                    ['Ada', 3],
                    ['Alan', 6]
                ]
            ]]
        )

    def test_max_aggregation_by_string_column(self):
        report_config = self._create_report(
            aggregation_columns=['indicator_col_id_number'],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_first_name",
                    "field": 'indicator_col_id_first_name',
                    'aggregation': 'max'
                },
                {
                    "type": "field",
                    "display": "report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'simple'
                }
            ],
            sort_expression=[
                {
                    "field": "report_column_col_id_number",
                    "order": "DESC"
                },
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                'foo',
                [
                    ['report_column_display_first_name', 'report_column_display_number'],
                    ['Alan', 4],
                    ['Ada', 3],
                    ['Alan', 2],
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
                'foo',
                [
                    ['report_column_display_percent'],
                    ['100%'],
                    ['100%'],
                    ['100%'],
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
                'foo',
                [
                    ['report_column_display_first_name', 'report_column_display_number'],
                    ['Ada', 3],
                    ['Alan', 6]
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
                'foo',
                [
                    ['indicator_col_id_first_name'],
                    ['Ada'],
                    ['Alan']
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
                'foo',
                [
                    ['indicator_col_id_first_name'],
                    ['Ada'],
                    ['Alan']
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
                'foo',
                [
                    ['indicator_col_id_first_name'],
                    ['Alan'],
                    ['Ada']
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
                'foo',
                [
                    [
                        'report_column_display_first_name',
                        'sum_report_column_display_number',
                        'min_report_column_display_number',
                    ],
                    ['Ada', 3, 3],
                    ['Alan', 6, 2],
                    ['Total', 9, ''],
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
                'foo',
                [
                    [
                        'report_column_display_first_name',
                        'sum_report_column_display_number',
                        'min_report_column_display_number',
                    ],
                    ['Ada', 3, 3],
                    ['Alan', 6, 2],
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
                'foo',
                [
                    [
                        'sum_report_column_display_number',
                        'report_column_display_first_name',
                        'min_report_column_display_number',
                    ],
                    [3, 'Ada', 3],
                    [6, 'Alan', 2],
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
                    'calculate_total': False,
                },
            ],
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                'foo',
                [
                    [
                        'sum_report_column_display_number',
                        'report_column_display_first_name-Ada',
                        'report_column_display_first_name-Alan',
                        'min_report_column_display_number',
                    ],
                    [3, 1, 0, 3],
                    [6, 0, 2, 2],
                    [9, 1, 2, ''],
                ]
            ]]
        )


class TestReportMultipleAggregationsSQL(ConfigurableReportTestMixin, TestCase):
    @classmethod
    def _create_data(cls):
        for row in [
            {"state": "MA", "city": "Boston", "number": 4, "age_at_registration": 1, "date": "2018-01-03"},
            {"state": "MA", "city": "Boston", "number": 3, "age_at_registration": 5, "date": "2018-02-18"},
            {"state": "MA", "city": "Cambridge", "number": 2, "age_at_registration": 8, "date": "2018-01-22"},
            {"state": "TN", "city": "Nashville", "number": 1, "age_at_registration": 14, "date": "2017-01-03"},
        ]:
            cls._new_case(row).save()

    @classmethod
    def _create_data_source(cls):
        cls.data_source = DataSourceConfiguration(
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
                        "property_name": 'state'
                    },
                    "column_id": 'indicator_col_id_state',
                    "display_name": 'indicator_display_name_state',
                    "datatype": "string"
                },
                # Except for column_id, this indicator is identical to the indicator above
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'state'
                    },
                    "column_id": 'report_column_col_id_state',
                    "display_name": 'indicator_display_name_state',
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'city'
                    },
                    "column_id": 'indicator_col_id_city',
                    "display_name": 'indicator_display_name_city',
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
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'age_at_registration'
                    },
                    "column_id": 'age_at_registration',
                    "datatype": "integer"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'date'
                    },
                    "column_id": 'date',
                    "datatype": "date"
                },
            ],
        )
        cls.data_source.validate()
        cls.data_source.save()
        rebuild_indicators(cls.data_source._id)
        adapter = get_indicator_adapter(cls.data_source)
        cls.adapter = adapter

    @classmethod
    def setUpClass(cls):
        super(TestReportMultipleAggregationsSQL, cls).setUpClass()
        cls._create_data()
        cls._create_data_source()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.drop_table()
        cls._delete_everything()
        super(TestReportMultipleAggregationsSQL, cls).tearDownClass()

    def _create_report(self, aggregation_columns, columns, filters=None):
        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=self.data_source._id,
            title='foo',
            aggregation_columns=aggregation_columns,
            columns=columns,
            filters=filters or [],
        )
        report_config.save()
        return report_config

    def _create_default_report(self, filters=None):
        return self._create_report(
            aggregation_columns=[
                'indicator_col_id_state',
                'indicator_col_id_city'
            ],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_state",
                    "field": 'indicator_col_id_state',
                    'column_id': 'report_column_col_id_state',
                    'aggregation': 'simple'
                },
                {
                    "type": "field",
                    "display": "report_column_display_city",
                    "field": 'indicator_col_id_city',
                    'column_id': 'report_column_col_id_city',
                    'aggregation': 'simple'
                },
                {
                    "type": "field",
                    "display": "report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'sum'
                }
            ],
            filters=filters,
        )

    def _create_view(self, report_config):
        view = ConfigurableReportView(request=HttpRequest())
        view._domain = self.domain
        view._lang = "en"
        view._report_config_id = report_config._id
        return view

    def test_with_multiple_agg_columns(self):
        report_config = self._create_default_report()
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                'foo',
                [
                    [
                        'report_column_display_state',
                        'report_column_display_city',
                        'report_column_display_number'
                    ],
                    ['MA', 'Boston', 7],
                    ['MA', 'Cambridge', 2],
                    ['TN', 'Nashville', 1],
                ]
            ]]
        )

    def test_aggregate_by_column_id_slash_data_source_indicator(self):
        # Aggregate by the report column_id, which also happens to be a column
        # in the data source. This has caused a bug in the past.
        report_config = self._create_report(
            aggregation_columns=[
                'report_column_col_id_state',
            ],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_state",
                    "field": 'indicator_col_id_state',
                    'column_id': 'report_column_col_id_state',
                    'aggregation': 'simple'
                },
                {
                    "type": "field",
                    "display": "report_column_display_number",
                    "field": 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'sum'
                }
            ],
        )
        view = self._create_view(report_config)

        table = view.export_table[0][1]
        self.assertEqual(len(table), 3)
        for table_row in [
            ['report_column_display_state', 'report_column_display_number'],
            ['MA', 9],
            ['TN', 1],
        ]:
            self.assertIn(table_row, table)

    def test_with_prefilter(self):
        report_config = self._create_default_report(
            filters=[
                {
                    "pre_value": "MA",
                    "datatype": "string",
                    "pre_operator": "=",
                    "display": "",
                    "field": "indicator_col_id_state",
                    "type": "pre",
                    "slug": "indicator_col_id_state_1"
                },
            ]
        )
        view = self._create_view(report_config)

        self.assertEqual(
            view.export_table,
            [[
                'foo',
                [
                    [
                        'report_column_display_state',
                        'report_column_display_city',
                        'report_column_display_number'
                    ],
                    ['MA', 'Boston', 7],
                    ['MA', 'Cambridge', 2],
                ]
            ]]
        )

    def test_aggregate_date(self):
        report_config = self._create_report(
            aggregation_columns=[
                'indicator_col_id_state',
                'month',
            ],
            columns=[
                {
                    'type': 'field',
                    'display': 'report_column_display_state',
                    'field': 'indicator_col_id_state',
                    'column_id': 'report_column_col_id_state',
                    'aggregation': 'simple'
                },
                {
                    'type': 'aggregate_date',
                    'display': 'month',
                    'field': 'date',
                    'column_id': 'month',
                    'aggregation': 'simple',
                    'format': '%Y-%m'
                },
                {
                    'type': 'field',
                    'display': 'report_column_display_number',
                    'field': 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'sum'
                }
            ],
            filters=None,
        )
        view = self._create_view(report_config)
        self.assertEqual(
            view.export_table,
            [['foo',
              [['report_column_display_state', 'month', 'report_column_display_number'],
               ['MA', '2018-01', 6],
               ['MA', '2018-02', 3],
               ['TN', '2017-01', 1]]]]
        )

    def test_conditional_aggregation(self):
        report_config = self._create_report(
            aggregation_columns=[
                'indicator_col_id_state',
                'age_range',
            ],
            columns=[
                {
                    'type': 'field',
                    'display': 'state',
                    'field': 'indicator_col_id_state',
                    'column_id': 'state',
                    'aggregation': 'simple'
                },
                {
                    'type': 'conditional_aggregation',
                    'display': 'age_range',
                    'column_id': 'age_range',
                    'whens': {
                        "age_at_registration between 0 and 6": "0-6",
                        "age_at_registration between 7 and 12": "7-12",
                    },
                    'else_': '13+'
                },
                {
                    'type': 'field',
                    'display': 'report_column_display_number',
                    'field': 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'sum'
                }
            ],
            filters=None,
        )
        view = self._create_view(report_config)
        table = view.export_table[0][1]
        self.assertEqual(len(table), 4)
        for table_row in [
            ['state', 'age_range', 'report_column_display_number'],
            ['MA', '0-6', 7],
            ['MA', '7-12', 2],
            ['TN', '13+', 1],
        ]:
            self.assertIn(table_row, table)

    def test_sum_when(self):
        report_config = self._create_report(
            aggregation_columns=[
                'indicator_col_id_state',
            ],
            columns=[
                {
                    'type': 'field',
                    'display': 'state',
                    'field': 'indicator_col_id_state',
                    'column_id': 'state',
                    'aggregation': 'simple'
                },
                {
                    'type': 'sum_when',
                    'display': 'under_six_month_olds',
                    'field': 'age_at_registration',
                    'column_id': 'under_six_month_olds',
                    'whens': {
                        "age_at_registration < 6": 1,
                    },
                    'else_': 0
                },
                {
                    'type': 'field',
                    'display': 'report_column_display_number',
                    'field': 'indicator_col_id_number',
                    'column_id': 'report_column_col_id_number',
                    'aggregation': 'sum'
                }
            ],
            filters=None,
        )
        view = self._create_view(report_config)
        table = view.export_table[0][1]
        self.assertEqual(len(table), 3)
        for table_row in [
            ['state', 'under_six_month_olds', 'report_column_display_number'],
            ['MA', 2, 9],
            ['TN', 0, 1],
        ]:
            self.assertIn(table_row, table)

    def test_doc_id_aggregation(self):
        # this uses a cheat to get all rows in the table
        # grouping on only doc_id works because PostgreSQL knows
        # it is a unique column
        # adding this is a workaround for sql-agg which would otherwise
        # only return the last row from the query results
        report_config = self._create_report(
            aggregation_columns=[
                'doc_id',
            ],
            columns=[
                {
                    "type": "field",
                    "display": "report_column_display_state",
                    "field": 'indicator_col_id_state',
                    'column_id': 'report_column_col_id_state',
                    'aggregation': 'simple'
                },
                {
                    "type": "field",
                    "display": "report_column_display_city",
                    "field": 'indicator_col_id_city',
                    'column_id': 'report_column_col_id_city',
                    'aggregation': 'simple'
                },
            ],
            filters=None,
        )
        view = self._create_view(report_config)
        table = view.export_table[0][1]
        self.assertEqual(len(table), 5)
        for table_row in [
            ['report_column_display_state', 'report_column_display_city'],
            ['MA', 'Boston'],
            ['MA', 'Boston'],
            ['MA', 'Cambridge'],
            ['TN', 'Nashville']
        ]:
            self.assertIn(table_row, table)
