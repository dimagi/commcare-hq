from django.test import SimpleTestCase
from corehq.apps.reports_core.filters import DatespanFilter
from corehq.apps.userreports.reports.factory import ReportFilterFactory


class DateFilterTestCase(SimpleTestCase):

    def testDateFilter(self):
        filter = ReportFilterFactory.from_spec({
            "type": "date",
            "field": "modified_on_field",
            "slug": "modified_on_slug",
            "display": "Date Modified"
        })
        self.assertEqual(DatespanFilter, type(filter))
        self.assertEqual('modified_on_slug', filter.name)
        self.assertEqual('Date Modified', filter.label)

