import random
import uuid
from datetime import datetime
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.stock import const as stockconst
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack import const
from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.hqcase.utils import get_cases_in_domain
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.commtrack.tests.util import make_loc, make_supply_point, make_supply_point_product
from corehq.apps.commtrack.tests.data.balances import (
    balance_ota_block,
    submission_wrap,
    balance_submission,
    transfer_dest_only,
    transfer_source_only,
    transfer_both,
    balance_first,
    transfer_first,
    create_requisition_xml,
    create_fulfillment_xml
)


class CommTrackOTATest(CommTrackTest):
    def test_ota_blank_balances(self):
        user = self.reporters['fixed']
        self.assertFalse(get_ota_balance_xml(user))

    def test_ota_basic(self):
        user = self.reporters['fixed']
        date = datetime.utcnow()
        report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=date, type=stockconst.REPORT_TYPE_BALANCE)
        amounts = [(p._id, i*10) for i, p in enumerate(self.products)]
        for product_id, amount in amounts:
            StockTransaction.objects.create(
                report=report,
                section_id='stock',
                case_id=self.sp._id,
                product_id=product_id,
                stock_on_hand=amount,
                quantity=amount,
            )

        check_xml_line_by_line(
            self,
            balance_ota_block(
                self.sp,
                'stock',
                amounts,
                datestring=json_format_datetime(date),
            ),
            get_ota_balance_xml(user)[0],
        )

    def test_ota_multiple_stocks(self):
        user = self.reporters['fixed']
        date = datetime.utcnow()
        report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=date,
                                            type=stockconst.REPORT_TYPE_BALANCE)
        amounts = [(p._id, i*10) for i, p in enumerate(self.products)]

        section_ids = sorted(('stock', 'losses', 'consumption'))
        for section_id in section_ids:
            for product_id, amount in amounts:
                StockTransaction.objects.create(
                    report=report,
                    section_id=section_id,
                    case_id=self.sp._id,
                    product_id=product_id,
                    stock_on_hand=amount,
                    quantity=amount,
                )

        balance_blocks = get_ota_balance_xml(user)
        self.assertEqual(3, len(balance_blocks))
        for i, section_id in enumerate(section_ids):
            check_xml_line_by_line(
                self,
                balance_ota_block(
                    self.sp,
                    section_id,
                    amounts,
                    datestring=json_format_datetime(date),
                ),
                balance_blocks[i],
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

    def check_stock_models(self, case, product_id, expected_soh, expected_qty, section_id):
        latest_trans = StockTransaction.latest(case._id, section_id, product_id)
        self.assertEqual(section_id, latest_trans.section_id)
        self.assertEqual(expected_soh, latest_trans.stock_on_hand)
        self.assertEqual(expected_qty, latest_trans.quantity)

    def check_product_stock(self, supply_point, product_id, expected_soh, expected_qty, section_id='stock'):
        # check the case
        if section_id == 'stock':
            spp = supply_point.get_product_subcase(product_id)
            self.assertEqual(expected_soh, spp.current_stock)

        # and the django model
        self.check_stock_models(supply_point, product_id, expected_soh, expected_qty, section_id)

    def setUp(self):
        super(CommTrackSubmissionTest, self).setUp()
        self.first_spp = self.spps[self.products[0].code]

        loc2 = make_loc('loc1')
        self.sp2 = make_supply_point(self.domain.name, loc2)
        self.second_spp = make_supply_point_product(self.sp2, self.products[0]._id)


class CommTrackBalanceTransferTest(CommTrackSubmissionTest):

    def test_balance_submit(self):
        amounts = [(p._id, float(i*10)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_submission(amounts))
        for product, amt in amounts:
            self.check_product_stock(self.sp, product, amt, 0)

    def test_balance_consumption(self):
        initial = float(100)
        initial_amounts = [(p._id, initial) for p in self.products]
        self.submit_xml_form(balance_submission(initial_amounts))

        final_amounts = [(p._id, float(50 - 10*i)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_submission(final_amounts))
        for product, amt in final_amounts:
            self.check_product_stock(self.sp, product, amt, 0)
            inferred = amt - initial
            inferred_txn = StockTransaction.objects.get(case_id=self.sp._id, product_id=product,
                                              subtype=stockconst.TRANSACTION_SUBTYPE_INFERRED)
            self.assertEqual(inferred, inferred_txn.quantity)
            self.assertEqual(amt, inferred_txn.stock_on_hand)
            self.assertEqual(stockconst.TRANSACTION_TYPE_CONSUMPTION, inferred_txn.type)

    def test_balance_submit_multiple_stocks(self):
        def _random_amounts():
            return [(p._id, float(random.randint(0, 100))) for i, p in enumerate(self.products)]

        section_ids = ('stock', 'losses', 'consumption')
        stock_amounts = [(id, _random_amounts()) for id in section_ids]
        for section_id, amounts in stock_amounts:
            self.submit_xml_form(balance_submission(amounts, section_id=section_id))

        for section_id, amounts in stock_amounts:
            for product, amt in amounts:
                self.check_product_stock(self.sp, product, amt, 0, section_id)

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

    def test_balance_first_doc_order(self):
        initial = float(100)
        balance_amounts = [(p._id, initial) for p in self.products]
        transfers = [(p._id, float(50 - 10*i)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_first(balance_amounts, transfers))
        for product, amt in transfers:
            self.check_product_stock(self.sp, product, initial + amt, amt)

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
            self.check_product_stock(self.sp, product, final, 0)


class CommTrackRequisitionTest(CommTrackSubmissionTest):

    def test_create_and_fulfill_requisition(self):
        amounts = [(p._id, 50.0 + float(i*10)) for i, p in enumerate(self.products)]
        self.submit_xml_form(create_requisition_xml(amounts))
        req_cases = list(get_cases_in_domain(self.domain.name, type=const.REQUISITION_CASE_TYPE))
        self.assertEqual(1, len(req_cases))
        req = req_cases[0]
        [index] = req.indices
        self.assertEqual(const.SUPPLY_POINT_CASE_TYPE, index.referenced_type)
        self.assertEqual(self.sp._id, index.referenced_id)
        self.assertEqual('parent_id', index.identifier)
        for product, amt in amounts:
            self.check_stock_models(req, product, amt, 0, 'stock')

        self.submit_xml_form(create_fulfillment_xml(req, amounts))

        for product, amt in amounts:
            self.check_stock_models(req, product, 0, -amt, 'stock')

        for product, amt in amounts:
            self.check_product_stock(self.sp, product, amt, amt, 'stock')
