from django.test import SimpleTestCase
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.factory import ReportFilterFactory, ChartFactory


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
