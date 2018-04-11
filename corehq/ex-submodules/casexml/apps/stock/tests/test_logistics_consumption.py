from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from decimal import Decimal

from datetime import datetime
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock.models import StockReport, StockTransaction
from casexml.apps.stock.tests.mock_consumption import ago
from casexml.apps.stock import const
from corehq.apps.commtrack.consumption import should_exclude_invalid_periods
from corehq.apps.commtrack.models import CommtrackConfig, ConsumptionConfig
from corehq.apps.domain.models import Domain
from corehq.apps.products.models import SQLProduct


class LogisticsConsumptionTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LogisticsConsumptionTest, cls).setUpClass()
        cls.domain = Domain(name='test')
        cls.domain.save()

        cls.case_id = uuid.uuid4().hex
        CommCareCase(
            _id=cls.case_id,
            domain='fakedomain',
        ).save()

        cls.product_id = uuid.uuid4().hex
        SQLProduct(product_id=cls.product_id, domain='fakedomain').save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(LogisticsConsumptionTest, cls).tearDownClass()

    def create_transactions(self, domain=None):
        report = StockReport.objects.create(
            form_id=uuid.uuid4().hex,
            date=ago(2),
            server_date=datetime.utcnow(),
            type=const.REPORT_TYPE_BALANCE,
            domain=domain
        )

        txn = StockTransaction(
            report=report,
            section_id=const.SECTION_TYPE_STOCK,
            type=const.TRANSACTION_TYPE_STOCKONHAND,
            case_id=self.case_id,
            product_id=self.product_id,
            stock_on_hand=Decimal(10),
        )
        txn.save()

        report2 = StockReport.objects.create(
            form_id=uuid.uuid4().hex,
            date=ago(1),
            server_date=datetime.utcnow(),
            type=const.REPORT_TYPE_BALANCE,
            domain=domain
        )

        txn2 = StockTransaction(
            report=report2,
            section_id=const.SECTION_TYPE_STOCK,
            type=const.TRANSACTION_TYPE_STOCKONHAND,
            case_id=self.case_id,
            product_id=self.product_id,
            stock_on_hand=Decimal(30),
        )
        txn2.save()

    def setUp(self):
        StockTransaction.objects.all().delete()
        StockReport.objects.all().delete()

    def tearDown(self):
        should_exclude_invalid_periods.clear(self.domain.name)
        should_exclude_invalid_periods.clear(None)

    def test_report_without_config(self):
        self.create_transactions(self.domain.name)
        self.assertEqual(StockTransaction.objects.all().count(), 3)
        receipts = StockTransaction.objects.filter(type='receipts')
        self.assertEqual(receipts.count(), 1)
        self.assertEqual(receipts[0].quantity, 20)

    def test_report_without_domain(self):
        self.create_transactions()
        self.assertEqual(StockTransaction.objects.all().count(), 3)
        receipts = StockTransaction.objects.filter(type='receipts')
        self.assertEqual(receipts.count(), 1)
        self.assertEqual(receipts[0].quantity, 20)

    def test_report_with_exclude_disabled(self):
        commtrack_config = CommtrackConfig(domain=self.domain.name)
        commtrack_config.consumption_config = ConsumptionConfig()
        commtrack_config.save()
        self.create_transactions(self.domain.name)
        self.assertEqual(StockTransaction.objects.all().count(), 3)
        self.assertEqual(StockTransaction.objects.filter(type='receipts').count(), 1)
        commtrack_config.delete()

    def test_report_with_exclude_enabled(self):
        commtrack_config = CommtrackConfig(domain=self.domain.name)
        commtrack_config.consumption_config = ConsumptionConfig(exclude_invalid_periods=True)
        commtrack_config.save()
        self.create_transactions(self.domain.name)
        self.assertEqual(StockTransaction.objects.all().count(), 2)
        self.assertEqual(StockTransaction.objects.filter(type='receipts').count(), 0)
        commtrack_config.delete()
