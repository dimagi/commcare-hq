import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.commtrack.tests.util import (
    get_single_balance_block,
    get_single_transfer_block,
    make_product,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.reports.analytics.couchaccessors import (
    get_ledger_values_for_case_as_of,
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
