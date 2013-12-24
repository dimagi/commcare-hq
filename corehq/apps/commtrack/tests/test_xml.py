import uuid
from datetime import datetime
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.stock.const import TRANSACTION_TYPE_BALANCE
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.commtrack.models import Product
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.commtrack.tests.util import make_loc, make_supply_point, make_supply_point_product
from corehq.apps.commtrack.tests.data.balances import (
    balances_with_adequate_values,
    submission_wrap,
    balance_submission,
    transfer_dest_only,
    transfer_source_only,
    transfer_both,
    transfer_neither,
    balance_first,
    transfer_first,
)


class CommTrackOTATest(CommTrackTest):
    def test_ota_blank_balances(self):
        user = self.reporters['fixed']
        self.assertFalse(get_ota_balance_xml(user))

    def test_ota_balances_with_adequate_values(self):
        user = self.reporters['fixed']
        date = datetime.utcnow()
        report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=date, type=TRANSACTION_TYPE_BALANCE)
        for product in self.products:
            StockTransaction.objects.create(
                report=report,
                case_id=self.sp._id,
                product_id=product._id,
                stock_on_hand=10,
                quantity=10,
            )

        check_xml_line_by_line(
            self,
            balances_with_adequate_values(
                self.sp,
                sorted(Product.by_domain(self.domain.name).all(), key=lambda p: p._id),
                datestring=json_format_datetime(date),
            ),
            get_ota_balance_xml(user),
        )

class CommTrackSubmissionTest(CommTrackTest):
    def submit_xml_form(self, xml_method):
        from casexml.apps.case import settings
        settings.CASEXML_FORCE_DOMAIN_CHECK = False
        instance = submission_wrap(
            self.products,
            self.reporters['fixed'],
            self.sp,
            self.sp2,
            xml_method,
        )
        submit_form_locally(
            instance=instance,
            domain=self.domain.name,
        )

    def check_product_stock(self, supply_point, product_id, expected_soh, expected_qty):
        # check the case
        spp = supply_point.get_product_subcase(product_id)
        self.assertEqual(expected_soh, spp.current_stock)

        # and the django model
        latest_trans = StockTransaction.latest(supply_point._id, product_id)
        self.assertEqual(expected_soh, latest_trans.stock_on_hand)
        self.assertEqual(expected_qty, latest_trans.quantity)

    def setUp(self):
        super(CommTrackSubmissionTest, self).setUp()
        self.first_spp = self.spps[self.products[0].code]

        loc2 = make_loc('loc1')
        self.sp2 = make_supply_point(self.domain.name, loc2)
        self.second_spp = make_supply_point_product(self.sp2, self.products[0]._id)

    def test_balance_submit(self):
        amounts = [(p._id, float(i*10)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_submission(amounts))
        for product, amt in amounts:
            self.check_product_stock(self.sp, product, amt, amt)

    def test_transfer_dest_only(self):
        amounts = [(p._id, float(i*10)) for i, p in enumerate(self.products)]
        self.submit_xml_form(transfer_dest_only(amounts))
        for product, amt in amounts:
            self.check_product_stock(self.sp, product, amt, amt)

    def test_transfer_source_only(self):
        initial = float(100)
        initial_amounts = [(p._id, initial) for p in self.products]
        self.submit_xml_form(balance_submission(initial_amounts))

        deductions = [(p._id, float(50 - 10*i)) for i, p in enumerate(self.products)]
        self.submit_xml_form(transfer_source_only(deductions))
        for product, amt in deductions:
            self.check_product_stock(self.sp, product, initial-amt, -amt)

    def test_transfer_both(self):
        initial = float(100)
        initial_amounts = [(p._id, initial) for p in self.products]
        self.submit_xml_form(balance_submission(initial_amounts))

        transfers = [(p._id, float(50 - 10*i)) for i, p in enumerate(self.products)]
        self.submit_xml_form(transfer_both(transfers))
        for product, amt in transfers:
            self.check_product_stock(self.sp, product, initial-amt, -amt)
            self.check_product_stock(self.sp2, product, amt, amt)

    def test_transfer_neither(self):
        # TODO this one should error
        # self.submit_xml_form(transfer_neither)
        pass

    def test_balance_first_doc_order(self):
        initial = float(100)
        balance_amounts = [(p._id, initial) for p in self.products]
        transfers = [(p._id, float(50 - 10*i)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_first(balance_amounts, transfers))
        for product, amt in transfers:
            self.check_product_stock(self.sp, product, initial+amt, amt)


    def test_transfer_first_doc_order(self):
        # first set to 100
        initial = float(100)
        initial_amounts = [(p._id, initial) for p in self.products]
        self.submit_xml_form(balance_submission(initial_amounts))

        # then mark some receipts
        transfers = [(p._id, float(50 - 10*i)) for i, p in enumerate(self.products)]
        # then set to 50
        final = float(50)
        balance_amounts = [(p._id, final) for p in self.products]
        self.submit_xml_form(transfer_first(transfers, balance_amounts))
        for product, amt in transfers:
            self.check_product_stock(self.sp, product, final, initial + amt - final)
