from decimal import Decimal
import uuid
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock.models import StockTransaction, StockReport
from casexml.apps.stock.tests.mock_consumption import ago
from casexml.apps.stock import const
from corehq.apps.products.models import SQLProduct

SUB_TYPE_MAX_LEN = 20


class StockTransactionTests(TestCase):

    def test_subtype_no_truncate(self):
        sub_type = 'a' * (SUB_TYPE_MAX_LEN - 1)
        self._test_subtype(sub_type, sub_type)

    def test_subtype_truncate(self):
        initial = 'a' * (SUB_TYPE_MAX_LEN + 3)
        final = 'a' * (SUB_TYPE_MAX_LEN)
        self._test_subtype(initial, final)

    def _test_subtype(self, initial, final):
        case_id = uuid.uuid4().hex
        CommCareCase(
            _id=case_id,
            domain='fakedomain',
        ).save()

        product_id = uuid.uuid4().hex
        SQLProduct(product_id=product_id, domain='fakedomain').save()
        report = StockReport.objects.create(
            form_id=uuid.uuid4().hex,
            date=ago(1),
            type=const.REPORT_TYPE_BALANCE
        )

        txn = StockTransaction(
            report=report,
            section_id=const.SECTION_TYPE_STOCK,
            type=const.TRANSACTION_TYPE_STOCKONHAND,
            subtype=initial,
            case_id=case_id,
            product_id=product_id,
            stock_on_hand=Decimal(10),
        )
        txn.save()

        saved = StockTransaction.objects.get(id=txn.id)
        self.assertEqual(final, saved.subtype)
