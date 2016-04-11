from django.test import TestCase
from crispy_forms.tests.utils import override_settings

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseFactory

from corehq.form_processor.tests import FormProcessorTestUtils
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL

DOMAIN = 'ledger-db-tests'


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class LedgerDBAccessorTest(TestCase):

    @classmethod
    def setUpClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        cls.product_a = make_product(DOMAIN, 'A Product', 'prodcode_a')
        cls.product_b = make_product(DOMAIN, 'B Product', 'prodcode_b')
        cls.product_c = make_product(DOMAIN, 'C Product', 'prodcode_c')

    def setUp(self):
        self.factory = CaseFactory(domain=DOMAIN)
        self.case_one = self.factory.create_case()
        self.case_two = self.factory.create_case()

    def _submit_ledgers(self, ledger_blocks):
        return submit_case_blocks(ledger_blocks, DOMAIN)

    def _set_balance(self, balance, case_id, product_id):
        from corehq.apps.commtrack.tests import get_single_balance_block
        self._submit_ledgers([
            get_single_balance_block(case_id, product_id, balance)
        ])

    def test_get_ledger_values_for_product_ids(self):
        self._set_balance(100, self.case_one.case_id, self.product_a._id)
        self._set_balance(200, self.case_two.case_id, self.product_b._id)

        values = LedgerAccessorSQL.get_ledger_values_for_product_ids([self.product_a._id])
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].case_id, self.case_one.case_id)

        values = LedgerAccessorSQL.get_ledger_values_for_product_ids(
            [self.product_a._id, self.product_b._id]
        )
        self.assertEqual(len(values), 2)
