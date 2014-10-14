from datetime import datetime
import random
import string

from django.test import TestCase

from corehq.apps.commtrack.models import NewStockReport

from casexml.apps.stock.const import REPORT_TYPE_BALANCE
from casexml.apps.stock.models import StockReport
from couchforms.models import XFormInstance


DOMAIN_MAX_LENGTH = 25


class StockReportDomainTest(TestCase):
    def _get_name_for_domain(self):
        return ''.join(
            random.choice(string.ascii_lowercase)
            for _ in range(DOMAIN_MAX_LENGTH)
        )

    def setUp(self):
        self.domain = self._get_name_for_domain()
        self.form = XFormInstance(domain=self.domain)
        self.form.save()
        self.new_stock_report = NewStockReport(
            self.form,
            datetime.now(),
            REPORT_TYPE_BALANCE,
            [],
        )

    def tearDown(self):
        self.form.delete()
        StockReport.objects.all().delete()

    def test_stock_report(self):
        self.new_stock_report.create_models()
        filtered_stock_report = StockReport.objects.filter(domain=self.domain)
        self.assertEquals(filtered_stock_report.count(), 1)
        stock_report = filtered_stock_report.get()
        self.assertEquals(stock_report.form_id, self.form._id)
        self.assertEquals(stock_report.domain, self.domain)
