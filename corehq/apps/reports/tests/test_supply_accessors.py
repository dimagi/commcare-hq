from __future__ import absolute_import, unicode_literals

import uuid
from datetime import datetime, timedelta

from django.test import TestCase
from django.test.utils import override_settings

from casexml.apps.case.mock import CaseFactory
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import (
    get_single_balance_block,
    get_single_transfer_block,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.reports.analytics.couchaccessors import (
    get_ledger_values_for_case_as_of,
)
from corehq.apps.reports.analytics.dbaccessors import (
    get_aggregated_ledger_values,
)
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    use_sql_backend,
)
from corehq.form_processor.utils import get_simple_form_xml


class TestSupplyAccessors(TestCase):
    domain = 'test-supply-accessors'

    @classmethod
    def setUpClass(cls):
        super(TestSupplyAccessors, cls).setUpClass()
        cls.product_a = make_product(cls.domain, 'A Product', 'prodcode_a')
        cls.product_b = make_product(cls.domain, 'B Product', 'prodcode_b')

    def test_get_ledger_values_for_case_as_of_no_data(self):
        self.assertEqual({}, get_ledger_values_for_case_as_of(domain=self.domain,
                                                              case_id='missing', section_id='stock',
                                                              as_of=datetime.utcnow()))

    # @run_with_all_backends
    def test_get_ledger_values_for_case_as_of(self):
        case_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(uuid.uuid4().hex, case_id)
        submit_form_locally(form_xml, domain=self.domain)[1]

        # submit ledger data
        balances = (
            (self.product_a._id, 100),
            (self.product_b._id, 50),
        )
        ledger_blocks = [
            get_single_balance_block(case_id, prod_id, balance)
            for prod_id, balance in balances
        ]
        submit_case_blocks(ledger_blocks, self.domain)

        # check results
        results = get_ledger_values_for_case_as_of(
            domain=self.domain, case_id=case_id, section_id='stock', as_of=datetime.utcnow())
        self.assertEqual(2, len(results))
        self.assertEqual(100, results[self.product_a._id])
        self.assertEqual(50, results[self.product_b._id])

        # check the date filter works
        before_data = datetime.utcnow() - timedelta(days=2)
        self.assertEqual({}, get_ledger_values_for_case_as_of(
            domain=self.domain, case_id=case_id, section_id='stock', as_of=before_data))

    def test_get_ledger_values_for_case_as_of_same_date(self):
        case_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(uuid.uuid4().hex, case_id)
        submit_form_locally(form_xml, domain=self.domain)[1]

        # submit ledger data
        balances = (
            (self.product_a._id, 100),
        )
        ledger_blocks = [
            get_single_balance_block(case_id, prod_id, balance)
            for prod_id, balance in balances
        ]
        submit_case_blocks(ledger_blocks, self.domain)

        # submit two transfers at the same time
        transfer_date = json_format_datetime(datetime.utcnow())
        transfers = [
            (self.product_a._id, 1, transfer_date),
            (self.product_a._id, 2, transfer_date),
        ]
        for prod_id, transfer, date in transfers:
            submit_case_blocks(get_single_transfer_block(case_id, None, prod_id, transfer, date), self.domain)

        # check results
        results = get_ledger_values_for_case_as_of(
            domain=self.domain, case_id=case_id, section_id='stock', as_of=datetime.utcnow())
        self.assertEqual(1, len(results))
        self.assertEqual(97, results[self.product_a._id])


@use_sql_backend
class LedgerDBAccessorTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LedgerDBAccessorTest, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        cls.product_a = make_product(cls.domain, 'A Product', 'prodcode_a')
        cls.product_b = make_product(cls.domain, 'B Product', 'prodcode_b')

    @classmethod
    def tearDownClass(cls):
        cls.product_a.delete()
        cls.product_b.delete()

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
        return submit_case_blocks(ledger_blocks, self.domain)[0].form_id

    def _set_balance(self, balance, case_id, product_id):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        return self._submit_ledgers([
            get_single_balance_block(case_id, product_id, balance)
        ])

    def _check_result(self, expected, entry_ids=None):
        result = []
        case_ids = [
            self.case_one.case_id,
            self.case_two.case_id,
        ]
        for row in get_aggregated_ledger_values(self.domain, case_ids, 'stock', entry_ids):
            result.append(row._asdict())
        self.assertItemsEqual(result, expected)

    def test_one_ledger(self):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, self.product_a._id, 1),
        ])
        self._check_result([
            {'entry_id': self.product_a._id, 'balance': 1}
        ])

    def test_two_ledger(self):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, self.product_a._id, 1),
            get_single_balance_block(self.case_two.case_id, self.product_a._id, 3),
        ])
        self._check_result([
            {'entry_id': self.product_a._id, 'balance': 4}
        ])

    def test_multiple_entries(self):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, self.product_a._id, 1),
            get_single_balance_block(self.case_two.case_id, self.product_a._id, 3),
            get_single_balance_block(self.case_one.case_id, self.product_b._id, 3),
        ])
        self._check_result([
            {'entry_id': self.product_b._id, 'balance': 3},
            {'entry_id': self.product_a._id, 'balance': 4},
        ])

    def test_filter_entries(self):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        self._submit_ledgers([
            get_single_balance_block(self.case_one.case_id, self.product_a._id, 1),
            get_single_balance_block(self.case_two.case_id, self.product_a._id, 3),
            get_single_balance_block(self.case_one.case_id, self.product_b._id, 3),
        ])
        self._check_result([
            {'entry_id': self.product_a._id, 'balance': 4},
        ], entry_ids=[self.product_a._id])
