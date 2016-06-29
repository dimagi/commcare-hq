import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests import get_single_balance_block
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.reports.analytics.couchaccessors import get_ledger_values_for_case_as_of
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
