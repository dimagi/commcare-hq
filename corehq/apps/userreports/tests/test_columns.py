from django.test import SimpleTestCase
from jsonobject.exceptions import BadValueError

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
            'month_name',
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
