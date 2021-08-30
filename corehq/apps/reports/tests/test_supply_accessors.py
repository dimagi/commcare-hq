import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.reports.analytics.dbaccessors import (
    get_aggregated_ledger_values,
)
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    sharded,
)


@sharded
class LedgerDBAccessorTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LedgerDBAccessorTest, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        cls.product_a = make_product(cls.domain, 'A Product', 'prodcode_a')
        cls.product_b = make_product(cls.domain, 'B Product', 'prodcode_b')

    @classmethod
    def tearDownClass(cls):
        cls.product_a.delete()
        cls.product_b.delete()

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
