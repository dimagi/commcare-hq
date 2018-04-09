from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal
from django.test import TestCase
from casexml.apps.case.tests.util import delete_all_xforms
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.sms import handle
from corehq.apps.commtrack.tests import util
from corehq.apps.products.models import Product
from corehq.apps.reminders.util import get_two_way_number_for_recipient
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.toggles import STOCK_AND_RECEIPT_SMS_HANDLER, NAMESPACE_DOMAIN
from couchforms.dbaccessors import get_commtrack_forms


class SMSTests(TestCase):
    user_definitions = []

    @classmethod
    def setUpClass(cls):
        super(SMSTests, cls).setUpClass()
        cls.backend, cls.backend_mapping = setup_default_sms_test_backend()
        cls.domain = util.bootstrap_domain(util.TEST_DOMAIN)
        util.bootstrap_location_types(cls.domain.name)
        util.bootstrap_products(cls.domain.name)
        cls.products = sorted(Product.by_domain(cls.domain.name), key=lambda p: p._id)
        cls.loc = util.make_loc('loc1')
        cls.sp = cls.loc.linked_supply_point()
        cls.users = [util.bootstrap_user(cls, **user_def) for user_def in cls.user_definitions]

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()  # domain delete cascades to everything else
        cls.backend_mapping.delete()
        cls.backend.delete()
        delete_all_users()
        super(SMSTests, cls).tearDownClass()

    def tearDown(self):
        delete_all_xforms()
        super(SMSTests, self).tearDown()

    def check_stock(self, code, amount, case_id=None, section_id='stock'):
        if not case_id:
            case_id = self.sp.case_id

        [product] = [p for p in self.products if p.code_ == code]

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
    user_definitions = [util.ROAMING_USER, util.FIXED_USER]

    def testStockReportRoaming(self):
        self.assertEqual(0, len(get_commtrack_forms(self.domain.name)))
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(get_two_way_number_for_recipient(self.users[0]), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ), None)
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
            [product] = [p for p in self.products if p.code_ == code]
            trans = StockTransaction.objects.get(product_id=product._id)
            self.assertEqual(self.sp.case_id, trans.case_id)
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
        handled = handle(get_two_way_number_for_recipient(self.users[1]), 'soh {report}'.format(
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ), None)
        self.assertTrue(handled)
        forms = list(get_commtrack_forms(self.domain.name))
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        for code, amt in amounts.items():
            [product] = [p for p in self.products if p.code_ == code]
            trans = StockTransaction.objects.get(product_id=product._id)
            self.assertEqual(self.sp.case_id, trans.case_id)
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
        handle(get_two_way_number_for_recipient(self.users[0]), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ), None)

        received_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(get_two_way_number_for_recipient(self.users[0]), 'r {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in received_amounts.items())
        ), None)

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
        handle(get_two_way_number_for_recipient(self.users[0]), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ), None)

        lost_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(get_two_way_number_for_recipient(self.users[0]), 'l {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ), None)

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
        handle(get_two_way_number_for_recipient(self.users[0]), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ), None)

        lost_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(get_two_way_number_for_recipient(self.users[0]), 'c {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ), None)

        self.assertTrue(handled)

        # this is the only difference from losses..
        self.check_form_type('consumption')

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] - lost_amounts[code]
            self.check_stock(code, expected_amount)


class StockAndReceiptTest(SMSTests):
    user_definitions = [util.FIXED_USER]

    def setUp(self):
        super(StockAndReceiptTest, self).setUp()
        STOCK_AND_RECEIPT_SMS_HANDLER.set(self.domain.name, True, NAMESPACE_DOMAIN)

    def test_soh_and_receipt(self):
        handled = handle(get_two_way_number_for_recipient(self.users[0]), 'pp 20.30', None)
        self.assertTrue(handled)

        self.check_stock('pp', Decimal(20))

    def tearDown(self):
        STOCK_AND_RECEIPT_SMS_HANDLER.set(self.domain.name, False, NAMESPACE_DOMAIN)
        super(StockAndReceiptTest, self).tearDown()


def _get_location_from_form(form):
    return form.form['location']


def _get_location_from_sp(sp):
    return sp.location_id
