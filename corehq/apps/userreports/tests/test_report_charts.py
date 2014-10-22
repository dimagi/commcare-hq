from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.factory import ChartFactory
from corehq.apps.userreports.reports.specs import PieChartSpec, MultibarChartSpec, MultibarAggregateChartSpec


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
                "property_no",
                "property_yes"
            ],
        })
        self.assertEqual(MultibarChartSpec, type(chart))

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
