from django.test import SimpleTestCase
from jsonobject.exceptions import BadValueError
from sqlagg import SumWhen
from corehq.apps.userreports.sql import _expand_column

from corehq.apps.userreports.reports.specs import ReportColumn


class TestReportColumn(SimpleTestCase):
    def testBadAggregation(self):
        with self.assertRaises(BadValueError):
            ReportColumn.wrap({
                "aggregation": "simple_",
                "field": "doc_id",
                "type": "field",
            })

    def testGoodFormat(self):
        for format in [
            'default',
            'percent_of_total',
        ]:
            self.assertEquals(ReportColumn, type(
                ReportColumn.wrap({
                    "aggregation": "simple",
                    "field": "doc_id",
                    "format": format,
                    "type": "field",
                })
            ))

    def testBadFormat(self):
        with self.assertRaises(BadValueError):
            ReportColumn.wrap({
                "aggregation": "simple",
                "field": "doc_id",
                "format": "default_",
                "type": "field",
            })


class TestExpandReportColumn(SimpleTestCase):

    def test_expansion(self):
        column = ReportColumn(
            type="field",
            field="lab_result",
            display="Lab Result",
            format="default",
            aggregation="expand",
            description="foo"
        )
        cols = _expand_column(column, ["positive", "negative"])

        self.assertEqual(len(cols), 2)
        self.assertEqual(type(cols[0].view), SumWhen)
        self.assertEqual(cols[1].view.whens, {'negative':1})
