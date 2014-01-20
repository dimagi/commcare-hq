import functools
import uuid
from django.test import TestCase
from casexml.apps.stock import const
from casexml.apps.stock.consumption import compute_consumption
from casexml.apps.stock.models import StockReport, StockTransaction
from casexml.apps.stock.tests.mock_consumption import ago, now


class StockTestBase(TestCase):

    def setUp(self):
        # create case
        self.case_id = uuid.uuid4()
        self.product_id = uuid.uuid4()
        self._stock_report = functools.partial(_stock_report, self.case_id, self.product_id)
        self._receipt_report = functools.partial(_receipt_report, self.case_id, self.product_id)
        self._compute_consumption = functools.partial(compute_consumption, self.case_id, self.product_id, now)


def _stock_report(case_id, product_id, amount, days_ago):
    report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=ago(days_ago),
                                        type=const.REPORT_TYPE_BALANCE)
    txn = StockTransaction(
        report=report,
        section_id=const.SECTION_TYPE_STOCK,
        type=const.TRANSACTION_TYPE_STOCKONHAND,
        case_id=case_id,
        product_id=product_id,
        stock_on_hand=amount,
    )
    txn.quantity = 0
    txn.save()


def _receipt_report(case_id, product_id, amount, days_ago):
    report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=ago(days_ago),
                                        type=const.REPORT_TYPE_TRANSFER)
    txn = StockTransaction(
        report=report,
        section_id=const.SECTION_TYPE_STOCK,
        type=const.TRANSACTION_TYPE_RECEIPTS,
        case_id=case_id,
        product_id=product_id,
        quantity=amount,
    )
    previous_transaction = txn.get_previous_transaction()
    txn.stock_on_hand = (previous_transaction.stock_on_hand if previous_transaction else 0) + txn.quantity
    txn.save()
