from django.test import TestCase

from casexml.apps.case.tests.util import delete_all_xforms
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS

from corehq.apps.commtrack.sms import handle
from corehq.apps.commtrack.tests import util
from corehq.apps.products.models import Product
from corehq.apps.reminders.util import get_two_way_number_for_recipient
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.form_processor.exceptions import LedgerValueNotFound
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, LedgerAccessorSQL


class SMSTests(TestCase):
    user_definitions = [util.ROAMING_USER, util.FIXED_USER]

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
            state = LedgerAccessorSQL.get_ledger_value(case_id, section_id, product._id)
            self.assertEqual(amount, state.stock_on_hand)
        except LedgerValueNotFound:
            if amount != 0:
                # only error if we weren't checking for no stock
                raise Exception(f'Ledger value for "{section_id}" section does not exist')

    def testStockReportRoaming(self):
        self.assertEqual([], list(iter_commtrack_forms(self.domain.name)))
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
        forms = list(iter_commtrack_forms(self.domain.name))
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        ledger_transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(self.sp.case_id)
        self.assertEqual({forms[0].form_id}, set(t.form_id for t in ledger_transactions))
        self.assertEqual({'balance'}, set(t.readable_type for t in ledger_transactions))
        self.assertEqual(3, len(ledger_transactions))

        self.check_transaction_amounts(ledger_transactions, amounts)

    def testStockReportFixed(self):
        self.assertEqual([], list(iter_commtrack_forms(self.domain.name)))
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
        forms = list(iter_commtrack_forms(self.domain.name))
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        ledger_transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(self.sp.case_id)
        self.check_transaction_amounts(ledger_transactions, amounts)

    def check_transaction_amounts(self, ledger_transactions, amounts):
        transactions_by_product_id = {t.entry_id: t for t in ledger_transactions}
        for code, amt in amounts.items():
            [product] = [p for p in self.products if p.code_ == code]
            trans = transactions_by_product_id[product._id]
            self.assertEqual(self.sp.case_id, trans.case_id)
            self.assertEqual(amt, trans.delta)
            self.assertEqual(amt, trans.updated_balance)

    def check_form_type(self, is_consumption):
        transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(self.sp.case_id)
        transactions = [t for t in transactions if t.readable_type != 'balance']
        self.assertEqual(3, len(transactions))
        for transaction in transactions:
            if is_consumption:
                self.assertLess(transaction.delta, 0)
            else:
                self.assertGreater(transaction.delta, 0)

    def testReceipt(self):
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

        self.check_form_type(is_consumption=False)

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] + received_amounts[code]
            self.check_stock(code, expected_amount)

    def testLosses(self):
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

        # First character in text indicates "loss"
        handled = handle(get_two_way_number_for_recipient(self.users[0]), 'l {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ), None)

        self.assertTrue(handled)

        self.check_form_type(is_consumption=True)

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] - lost_amounts[code]
            self.check_stock(code, expected_amount)

    def testConsumption(self):
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

        # First character in text indicates "consumption"
        handled = handle(get_two_way_number_for_recipient(self.users[0]), 'c {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ), None)

        self.assertTrue(handled)

        self.check_form_type(is_consumption=True)

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] - lost_amounts[code]
            self.check_stock(code, expected_amount)


def iter_commtrack_forms(domain_name):
    for form_id in FormAccessorSQL.iter_form_ids_by_xmlns(domain_name, COMMTRACK_REPORT_XMLNS):
        yield FormAccessorSQL.get_form(form_id)


def _get_location_from_form(form):
    return form.form_data['location']


def _get_location_from_sp(sp):
    return sp.location_id
