from decimal import Decimal
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.tests.util import CommTrackTest, FIXED_USER, ROAMING_USER
from corehq.apps.commtrack.sms import handle
from corehq.toggles import STOCK_AND_RECEIPT_SMS_HANDLER, NAMESPACE_DOMAIN
from couchforms.dbaccessors import get_commtrack_forms


class SMSTests(CommTrackTest):
    def setUp(self):
        super(SMSTests, self).setUp()

    def check_stock(self, code, amount, case_id=None, section_id='stock'):
        if not case_id:
            case_id = self.sp._id

        [product] = filter(lambda p: p.code_ == code, self.products)

        try:
            state = StockState.objects.get(
                product_id=product._id,
                case_id=case_id,
                section_id=section_id
            )
            self.assertEqual(amount, state.stock_on_hand)
        except StockState.DoesNotExist:
            if amount != 0:
                # only error if we weren't checking for no stock
                raise Exception(
                    'StockState for "%s" section does not exist' % section_id
                )


class StockReportTest(SMSTests):
    user_definitions = [ROAMING_USER, FIXED_USER]

    def testStockReportRoaming(self):
        self.assertEqual(0, len(get_commtrack_forms(self.domain.name)))
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        forms = list(get_commtrack_forms(self.domain.name))
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        self.assertEqual(1, StockReport.objects.count())
        report = StockReport.objects.all()[0]
        self.assertEqual(forms[0]._id, report.form_id)
        self.assertEqual('balance', report.type)
        self.assertEqual(3, report.stocktransaction_set.count())

        for code, amt in amounts.items():
            [product] = filter(lambda p: p.code_ == code, self.products)
            trans = StockTransaction.objects.get(product_id=product._id)
            self.assertEqual(self.sp._id, trans.case_id)
            self.assertEqual(0, trans.quantity)
            self.assertEqual(amt, trans.stock_on_hand)

    def testStockReportFixed(self):
        self.assertEqual(0, len(get_commtrack_forms(self.domain.name)))

        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.users[1].get_verified_number(), 'soh {report}'.format(
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        forms = list(get_commtrack_forms(self.domain.name))
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        for code, amt in amounts.items():
            [product] = filter(lambda p: p.code_ == code, self.products)
            trans = StockTransaction.objects.get(product_id=product._id)
            self.assertEqual(self.sp._id, trans.case_id)
            self.assertEqual(0, trans.quantity)
            self.assertEqual(amt, trans.stock_on_hand)

    def check_form_type(self, expected_type, subtype=None):
        [report] = StockReport.objects.filter(type='transfer')
        transaction = report.stocktransaction_set.all()[0]
        self.assertEqual(
            transaction.type,
            expected_type
        )
        if subtype:
            self.assertEqual(
                transaction.subtype,
                subtype
            )

    def testStockReceipt(self):
        original_amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # First submit an soh so we can make sure receipts functions
        # differently than soh
        handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ))

        received_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(self.users[0].get_verified_number(), 'r {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in received_amounts.items())
        ))

        self.assertTrue(handled)

        self.check_form_type('receipts')

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] + received_amounts[code]
            self.check_stock(code, expected_amount)

    def testStockLosses(self):
        original_amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # First submit an soh so we can make sure losses functions properly
        handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ))

        lost_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(self.users[0].get_verified_number(), 'l {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ))

        self.assertTrue(handled)

        self.check_form_type('consumption', 'loss')

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] - lost_amounts[code]
            self.check_stock(code, expected_amount)

    def testStockConsumption(self):
        original_amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # First submit an soh so we can make sure consumption functions properly
        handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ))

        lost_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(self.users[0].get_verified_number(), 'c {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ))

        self.assertTrue(handled)

        # this is the only difference from losses..
        self.check_form_type('consumption')

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] - lost_amounts[code]
            self.check_stock(code, expected_amount)


class StockAndReceiptTest(SMSTests):
    user_definitions = [FIXED_USER]

    def setUp(self):
        super(StockAndReceiptTest, self).setUp()
        STOCK_AND_RECEIPT_SMS_HANDLER.set(self.domain, True, NAMESPACE_DOMAIN)

    def test_soh_and_receipt(self):
        handled = handle(self.users[0].get_verified_number(), 'pp 20.30')
        self.assertTrue(handled)

        self.check_stock('pp', Decimal(20))

    def tearDown(self):
        super(StockAndReceiptTest, self).tearDown()
        STOCK_AND_RECEIPT_SMS_HANDLER.set(self.domain, False, NAMESPACE_DOMAIN)



def _get_location_from_form(form):
    return form.form['location']

def _get_location_from_sp(sp):
    return sp.location_id
