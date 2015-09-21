from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.commtrack.models import StockState
from couchforms.models import XFormInstance
from custom.ewsghana.tests.handlers.utils import EWSScriptTest, TEST_DOMAIN


class TestUndo(EWSScriptTest):

    def tearDown(self):
        for xform in XFormInstance.view(
            'reports_forms/all_forms',
            startkey=['submission', TEST_DOMAIN],
            endkey=['submission', TEST_DOMAIN, {}],
            reduce=False,
            include_docs=True,
        ):
            xform.delete()

    def test_no_product_reports(self):
        a = """
            5551234 > undo
            5551234 < You have not submitted any product reports yet.
        """
        self.run_script(a)

    def test_undo_messages(self):
        a = """
           5551234 > soh ov 16.0
           5551234 < Dear test1 test1, thank you for reporting the commodities you have in stock.
           5551234 > undo
           5551234 < Success. Your previous report has been removed. It was: soh ov 16.0
           5551234 > undo
           5551234 < You have not submitted any product reports yet.
           """
        self.run_script(a)

    def test_undo_data1(self):
        a = """
           5551234 > soh ov 16.0
           5551234 < Dear test1 test1, thank you for reporting the commodities you have in stock.
           5551234 > soh ov 10.0
           5551234 < Dear test1 test1, thank you for reporting the commodities you have in stock.
           """
        self.run_script(a)

        transactions_count = StockTransaction.objects.filter(
            type='stockonhand', report__domain=TEST_DOMAIN
        ).count()
        reports = StockReport.objects.filter(domain=TEST_DOMAIN).count()

        a = """
           5551234 > undo
           5551234 < Success. Your previous report has been removed. It was: soh ov 10.0
           """
        self.run_script(a)

        self.assertEqual(
            StockTransaction.objects.filter(type='stockonhand', report__domain=TEST_DOMAIN).count(),
            transactions_count - 1
        )

        self.assertEqual(
            StockReport.objects.filter(domain=TEST_DOMAIN).count(), reports - 2
        )

        self.assertEqual(int(StockState.objects.get(sql_product__code='ov').stock_on_hand), 16)

    def test_undo_data2(self):
        a = """
           5551234 > soh ov 16.0 ml 8.0
           5551234 < Dear test1 test1, thank you for reporting the commodities you have in stock.
           5551234 > soh ov 10.0 ml 5.0
           5551234 < Dear test1 test1, thank you for reporting the commodities you have in stock.
           """
        self.run_script(a)

        transactions_count = StockTransaction.objects.filter(
            type='stockonhand', report__domain=TEST_DOMAIN
        ).count()
        reports = StockReport.objects.filter(domain=TEST_DOMAIN).count()

        a = """
           5551234 > undo
           5551234 < Success. Your previous report has been removed. It was: soh ml 5.0 ov 10.0
           """
        self.run_script(a)

        self.assertEqual(
            StockTransaction.objects.filter(type='stockonhand', report__domain=TEST_DOMAIN).count(),
            transactions_count - 2
        )

        self.assertEqual(
            StockReport.objects.filter(domain=TEST_DOMAIN).count(), reports - 2
        )

        self.assertEqual(int(StockState.objects.get(sql_product__code='ml').stock_on_hand), 8)
