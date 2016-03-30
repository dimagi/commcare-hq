import functools
import uuid
from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from casexml.apps.stock.consumption import compute_daily_consumption, ConsumptionConfiguration
from casexml.apps.stock.tests.mock_consumption import ago, now
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.products.models import SQLProduct


class StockTestBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain("stock-report-test")

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

    def setUp(self):
        # create case
        case = CaseFactory(domain=self.domain.name).create_case()
        self.case_id = case.case_id

        self.product_id = uuid.uuid4().hex
        SQLProduct(product_id=self.product_id, domain=self.domain.name).save()
        self._stock_report = functools.partial(_stock_report, self.domain.name, self.case_id, self.product_id)
        self._receipt_report = functools.partial(_receipt_report, self.domain.name, self.case_id, self.product_id)
        self._test_config = ConsumptionConfiguration.test_config()
        self._compute_consumption = functools.partial(
            compute_daily_consumption, self.domain.name, self.case_id,
            self.product_id, now, configuration=self._test_config
        )

    def tearDown(self):
        from corehq.form_processor.tests import FormProcessorTestUtils
        FormProcessorTestUtils.delete_all_xforms(self.domain.name)
        FormProcessorTestUtils.delete_all_cases(self.domain.name)


def _stock_report(domain, case_id, product_id, amount, days_ago):
    from corehq.apps.commtrack.tests import get_single_balance_block
    from corehq.apps.hqcase.utils import submit_case_blocks
    from dimagi.utils.parsing import json_format_date
    date_string = json_format_date(ago(days_ago))
    stock_block = get_single_balance_block(
        case_id=case_id, product_id=product_id, quantity=amount, date_string=date_string
    )
    submit_case_blocks(stock_block, domain=domain)


def _receipt_report(domain, case_id, product_id, amount, days_ago):
    from corehq.apps.commtrack.tests import get_single_transfer_block
    from dimagi.utils.parsing import json_format_date
    from corehq.apps.hqcase.utils import submit_case_blocks
    date_string = json_format_date(ago(days_ago))
    stock_block = get_single_transfer_block(
        src_id=None, dest_id=case_id, product_id=product_id, quantity=amount, date_string=date_string
    )
    submit_case_blocks(stock_block, domain=domain)
