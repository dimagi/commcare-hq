import uuid

from datetime import datetime

import time
from django.test import TestCase
from django.test.utils import override_settings

from corehq.form_processor.exceptions import LedgerSaveError

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseFactory
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference

from corehq.form_processor.tests import FormProcessorTestUtils
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class LedgerDBAccessorTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LedgerDBAccessorTest, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        cls.product_a = make_product(cls.domain, 'A Product', 'prodcode_a')
        cls.product_b = make_product(cls.domain, 'B Product', 'prodcode_b')
        cls.product_c = make_product(cls.domain, 'C Product', 'prodcode_c')

    @classmethod
    def tearDownClass(cls):
        cls.product_a.delete()
        cls.product_b.delete()
        cls.product_c.delete()

        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        super(LedgerDBAccessorTest, cls).tearDownClass()

    def setUp(self):
        super(LedgerDBAccessorTest, self).setUp()
        self.factory = CaseFactory(domain=self.domain)
        self.case_one = self.factory.create_case()
        self.case_two = self.factory.create_case()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_ledgers(self.domain)
        super(LedgerDBAccessorTest, self).tearDown()

    def _submit_ledgers(self, ledger_blocks):
        return submit_case_blocks(ledger_blocks, self.domain).form_id

    def _set_balance(self, balance, case_id, product_id):
        from corehq.apps.commtrack.tests import get_single_balance_block
        return self._submit_ledgers([
            get_single_balance_block(case_id, product_id, balance)
        ])

    def test_delete_ledger_transactions_for_form(self):
        from corehq.apps.commtrack.tests import get_single_balance_block

        self._set_balance(100, self.case_one.case_id, self.product_a._id)

        case_ids = [self.case_one.case_id, self.case_two.case_id]
        form_id = self._submit_ledgers([
            get_single_balance_block(case_id, product_id, 10)
            for case_id in case_ids
            for product_id in [self.product_a._id, self.product_b._id]
        ])
        deleted = LedgerAccessorSQL.delete_ledger_transactions_for_form(case_ids, form_id)
        self.assertEqual(4, deleted)
        self.assertEqual(
            1,
            len(LedgerAccessorSQL.get_ledger_transactions_for_case(self.case_one.case_id))
        )
        self.assertEqual(
            0,
            len(LedgerAccessorSQL.get_ledger_transactions_for_case(self.case_two.case_id))
        )

    def test_delete_ledger_values_case_section_entry(self):
        from corehq.apps.commtrack.tests import get_single_balance_block
        form_id = self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, product_id, 10)
            for product_id in [self.product_a._id, self.product_b._id]
        ])
        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(2, len(ledger_values))

        LedgerAccessorSQL.delete_ledger_transactions_for_form([self.case_one.case_id], form_id)
        deleted = LedgerAccessorSQL.delete_ledger_values(self.case_one.case_id, 'stock', self.product_a._id)
        self.assertEqual(1, deleted)

        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(1, len(ledger_values))
        self.assertEqual(self.product_b._id, ledger_values[0].product_id)

    def test_delete_ledger_values_case_section(self):
        from corehq.apps.commtrack.tests import get_single_balance_block
        form_id = self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, product_id, 10)
            for product_id in [self.product_a._id, self.product_b._id]
        ])
        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(2, len(ledger_values))

        LedgerAccessorSQL.delete_ledger_transactions_for_form([self.case_one.case_id], form_id)
        deleted = LedgerAccessorSQL.delete_ledger_values(self.case_one.case_id, 'stock')
        self.assertEqual(2, deleted)

        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(0, len(ledger_values))

    def test_delete_ledger_values_case_section_1(self):
        from corehq.apps.commtrack.tests import get_single_balance_block
        form_id = self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, self.product_a._id, 10, section_id=section_id)
            for section_id in ['stock', 'consumption']
        ])
        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(2, len(ledger_values))

        LedgerAccessorSQL.delete_ledger_transactions_for_form([self.case_one.case_id], form_id)
        deleted = LedgerAccessorSQL.delete_ledger_values(self.case_one.case_id, 'stock')
        self.assertEqual(1, deleted)

        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(1, len(ledger_values))
        self.assertEqual('consumption', ledger_values[0].section_id)

    def test_delete_ledger_values_case(self):
        from corehq.apps.commtrack.tests import get_single_balance_block
        form_id = self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, product_id, 10, section_id=section_id)
            for product_id in [self.product_a._id, self.product_b._id]
            for section_id in ['stock', 'consumption']
        ])
        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(4, len(ledger_values))

        LedgerAccessorSQL.delete_ledger_transactions_for_form([self.case_one.case_id], form_id)
        deleted = LedgerAccessorSQL.delete_ledger_values(self.case_one.case_id)
        self.assertEqual(4, deleted)

        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case_one.case_id)
        self.assertEqual(0, len(ledger_values))

    def test_get_all_ledgers_modified_since(self):
        FormProcessorTestUtils.delete_all_ledgers()

        self._set_balance(100, self.case_one.case_id, self.product_a._id)
        self._set_balance(100, self.case_one.case_id, self.product_b._id)
        self._set_balance(100, self.case_one.case_id, self.product_c._id)
        middle = datetime.utcnow()
        time.sleep(.01)
        self._set_balance(100, self.case_two.case_id, self.product_a._id)
        self._set_balance(100, self.case_two.case_id, self.product_b._id)
        self._set_balance(100, self.case_two.case_id, self.product_c._id)
        time.sleep(.01)
        end = datetime.utcnow()

        ledgers_back = list(LedgerAccessorSQL.get_all_ledgers_modified_since(chunk_size=2))
        self.assertEqual(6, len(ledgers_back))
        ledger_references = [
            UniqueLedgerReference(self.case_one.case_id, 'stock', self.product_a._id),
            UniqueLedgerReference(self.case_one.case_id, 'stock', self.product_b._id),
            UniqueLedgerReference(self.case_one.case_id, 'stock', self.product_c._id),
            UniqueLedgerReference(self.case_two.case_id, 'stock', self.product_a._id),
            UniqueLedgerReference(self.case_two.case_id, 'stock', self.product_b._id),
            UniqueLedgerReference(self.case_two.case_id, 'stock', self.product_c._id),
        ]
        self.assertEqual(
            set(ledger.ledger_reference for ledger in ledgers_back),
            set(ledger_references)
        )

        ledgers_back = list(LedgerAccessorSQL.get_all_ledgers_modified_since(middle, chunk_size=2))
        self.assertEqual(3, len(ledgers_back))
        self.assertEqual(set(ledger.ledger_reference for ledger in ledgers_back),
                         set(ledger_references[3:]))

        self.assertEqual(0, len(list(LedgerAccessorSQL.get_all_ledgers_modified_since(end))))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class LedgerAccessorErrorTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(LedgerAccessorErrorTests, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.product = make_product(cls.domain, 'A Product', 'prodcode_a')

    def setUp(self):
        # can't do this in setUpClass until Django 1.9 since @override_settings
        # doesn't apply to classmethods
        from corehq.apps.commtrack.tests import get_single_balance_block
        factory = CaseFactory(domain=self.domain)
        self.case = factory.create_case()
        submit_case_blocks([
            get_single_balance_block(self.case.case_id, self.product._id, 10)
        ], self.domain)

        ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(self.case.case_id)
        self.assertEqual(1, len(ledger_values))

    @classmethod
    def tearDownClass(cls):
        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        cls.product.delete()
        super(LedgerAccessorErrorTests, cls).tearDownClass()

    def test_delete_ledger_values_raise_error_case_section_entry(self):
        with self.assertRaisesRegexp(LedgerSaveError, '.*still has transactions.*'):
            LedgerAccessorSQL.delete_ledger_values(self.case.case_id, 'stock', self.product._id)

    def test_delete_ledger_values_raise_error_case_section(self):
        with self.assertRaisesRegexp(LedgerSaveError, '.*still has transactions.*'):
            LedgerAccessorSQL.delete_ledger_values(self.case.case_id, 'stock')

    def test_delete_ledger_values_raise_error_case(self):
        with self.assertRaisesRegexp(LedgerSaveError, '.*still has transactions.*'):
            LedgerAccessorSQL.delete_ledger_values(self.case.case_id)
