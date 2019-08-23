from django.test import SimpleTestCase
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.factory import ChartFactory
from corehq.apps.userreports.reports.specs import PieChartSpec, MultibarChartSpec, MultibarAggregateChartSpec, \
    GraphDisplayColumn


class ChartTestCase(SimpleTestCase):

    def test_no_type(self):
        with self.assertRaises(BadSpecError):
            ChartFactory.from_spec({
                "title": "Chart Title",
                "aggregation_column": "agg_col",
                "value_column": "count",
            })

    def test_bad_type(self):
        with self.assertRaises(BadSpecError):
            ChartFactory.from_spec({
                "type": "invalid_type",
                "title": "Chart Title",
                "aggregation_column": "agg_col",
                "value_column": "count",
            })


class PieChartTestCase(SimpleTestCase):

    def test_make_pie_chart(self):
        chart = ChartFactory.from_spec({
            "type": "pie",
            "title": "Chart Title",
            "aggregation_column": "agg_col",
            "value_column": "count",
        })
        self.assertEqual(PieChartSpec, type(chart))

    def test_missing_value(self):
        with self.assertRaises(BadSpecError):
            ChartFactory.from_spec({
                "type": "pie",
                "title": "Chart Title",
                "aggregation_column": "agg_col",
            })


class MultibarTestCase(SimpleTestCase):

    def test_make_multibar_chart(self):
        chart = ChartFactory.from_spec({
            "type": "multibar",
            "title": "Property Matches by clinic",
            "x_axis_column": "clinic",
            "y_axis_columns": [
                {
                    "column_id": "property_no",
                    "display": "No"
                },
                {
                    "column_id": "property_yes",
                    "display": "Yes"
                }
            ],
        })
        self.assertEqual(MultibarChartSpec, type(chart))

    def test_make_multibar_chart_legacy_columns(self):
        chart = ChartFactory.from_spec({
            "type": "multibar",
            "title": "Property Matches by clinic",
            "x_axis_column": "clinic",
            "y_axis_columns": [
                "property_no",
                {"column_id": "property_yes"}
            ],
        })
        self.assertEqual(MultibarChartSpec, type(chart))
        col_0, col_1 = chart.y_axis_columns
        self.assertTrue(isinstance(col_0, GraphDisplayColumn))
        self.assertEqual('property_no', col_0.display)
        self.assertEqual('property_no', col_0.column_id)
        self.assertTrue(isinstance(col_1, GraphDisplayColumn))
        self.assertEqual('property_yes', col_1.display)
        self.assertEqual('property_yes', col_1.column_id)

    def test_make_multibar_chart_bad_columns(self):
        for test_case in [None, 5, [], {}, {"display": "missing column id"}]:
            with self.assertRaises(BadSpecError):
                ChartFactory.from_spec({
                    "type": "multibar",
                    "title": "Property Matches by clinic",
                    "x_axis_column": "clinic",
                    "y_axis_columns": [test_case],
                })

    def test_missing_x_axis(self):
        with self.assertRaises(BadSpecError):
            ChartFactory.from_spec({
                "type": "multibar",
                "title": "Property Matches by clinic",
                "y_axis_columns": [
                    "property_no",
                    "property_yes"
                ],
            })


class MultibarAggregateTestCase(SimpleTestCase):

    def test_make_multibar_chart(self):
        chart = ChartFactory.from_spec({
            "type": "multibar-aggregate",
            "title": "Applicants by type and location",
            "primary_aggregation": "remote",
            "secondary_aggregation": "applicant_type",
            "value_column": "count",
        })
        self.assertEqual(MultibarAggregateChartSpec, type(chart))

    def test_missing_value(self):
        with self.assertRaises(BadSpecError):
            ChartFactory.from_spec({
                "type": "multibar-aggregate",
                "title": "Applicants by type and location",
                "primary_aggregation": "remote",
                "secondary_aggregation": "applicant_type",
            })

    def test_missing_primary(self):
        with self.assertRaises(BadSpecError):
            ChartFactory.from_spec({
                "type": "multibar-aggregate",
                "title": "Applicants by type and location",
                "secondary_aggregation": "applicant_type",
                "value_column": "count",
            })

    def test_missing_secondary(self):
        with self.assertRaises(BadSpecError):
            ChartFactory.from_spec({
                "type": "multibar-aggregate",
                "title": "Applicants by type and location",
                "primary_aggregation": "remote",
                "value_column": "count",
            })


class ChartJsonTest(SimpleTestCase):

    def test_charts_to_json(self):
        # this tests a regression - namely that calling to_json on a chart config
        # when accessed via a report would crash.
        report = ReportConfiguration(configured_charts=[
            dict(
                type='pie',
                value_column='count',
                aggregation_column='remote',
                title='Remote status'
            )
        ])
        chart = report.charts[0]
        chart.to_json()  # this is the line that used to crash
