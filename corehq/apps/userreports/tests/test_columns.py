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
