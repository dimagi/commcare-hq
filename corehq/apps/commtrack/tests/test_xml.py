import random
import uuid
from datetime import datetime
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.restore import RestoreConfig
from casexml.apps.phone.tests import synclog_from_restore_payload
from casexml.apps.phone.tests.utils import synclog_id_from_restore_payload
from corehq.apps.commtrack.models import ConsumptionConfig, StockRestoreConfig
from corehq.apps.consumption.shortcuts import set_default_consumption_for_domain
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.stock import const as stockconst
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack import const
from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml, FIXED_USER, extract_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line, check_user_has_case
from corehq.apps.hqcase.utils import get_cases_in_domain
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.commtrack.tests.util import make_loc, make_supply_point
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
    create_fulfillment_xml,
    receipts_enumerated,
    balance_enumerated
)


class CommTrackOTATest(CommTrackTest):
    user_definitions = [FIXED_USER]

    def setUp(self):
        super(CommTrackOTATest, self).setUp()
        self.user = self.users[0]

    def test_ota_blank_balances(self):
        user = self.user
        self.assertFalse(get_ota_balance_xml(user))

    def test_ota_basic(self):
        user = self.user
        amounts = [(p._id, i*10) for i, p in enumerate(self.products)]
        report = _report_soh(amounts, self.sp._id, 'stock')
        check_xml_line_by_line(
            self,
            balance_ota_block(
                self.sp,
                'stock',
                amounts,
                datestring=json_format_datetime(report.date),
            ),
            get_ota_balance_xml(user)[0],
        )

    def test_ota_multiple_stocks(self):
        user = self.user
        date = datetime.utcnow()
        report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=date,
                                            type=stockconst.REPORT_TYPE_BALANCE)
        amounts = [(p._id, i*10) for i, p in enumerate(self.products)]

        section_ids = sorted(('stock', 'losses', 'consumption'))
        for section_id in section_ids:
            _report_soh(amounts, self.sp._id, section_id, report=report)

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

    def test_ota_consumption(self):
        self.ct_settings.consumption_config = ConsumptionConfig(
            min_transactions=0,
            min_window=0,
            optimal_window=60,
        )
        self.ct_settings.ota_restore_config = StockRestoreConfig(
            section_to_consumption_types={'stock': 'consumption'}
        )
        set_default_consumption_for_domain(self.domain.name, 5)
        ota_settings = self.ct_settings.get_ota_restore_settings()

        amounts = [(p._id, i*10) for i, p in enumerate(self.products)]
        report = _report_soh(amounts, self.sp._id, 'stock')
        restore_config = RestoreConfig(
            self.user.to_casexml_user(),
            version=V2,
            stock_settings=ota_settings,
        )
        balance_blocks = extract_balance_xml(restore_config.get_payload())
        self.assertEqual(2, len(balance_blocks))
        stock_block, consumption_block = balance_blocks
        check_xml_line_by_line(
            self,
            balance_ota_block(
                self.sp,
                'stock',
                amounts,
                datestring=json_format_datetime(report.date),
            ),
            stock_block,
        )
        check_xml_line_by_line(
            self,
            balance_ota_block(
                self.sp,
                'consumption',
                [(p._id, 5) for p in self.products],
                datestring=json_format_datetime(report.date),
            ),
             consumption_block,
        )


class CommTrackSubmissionTest(CommTrackTest):
    user_definitions = [FIXED_USER]

    def setUp(self):
        super(CommTrackSubmissionTest, self).setUp()
        self.user = self.users[0]
        loc2 = make_loc('loc1')
        self.sp2 = make_supply_point(self.domain.name, loc2)

    def submit_xml_form(self, xml_method, **submit_extras):
        from casexml.apps.case import settings
        settings.CASEXML_FORCE_DOMAIN_CHECK = False
        instance = submission_wrap(
            self.products,
            self.user,
            self.sp,
            self.sp2,
            xml_method,
        )
        submit_form_locally(
            instance=instance,
            domain=self.domain.name,
            **submit_extras
        )

    def check_stock_models(self, case, product_id, expected_soh, expected_qty, section_id):
        latest_trans = StockTransaction.latest(case._id, section_id, product_id)
        self.assertEqual(section_id, latest_trans.section_id)
        self.assertEqual(expected_soh, latest_trans.stock_on_hand)
        self.assertEqual(expected_qty, latest_trans.quantity)

    def check_product_stock(self, supply_point, product_id, expected_soh, expected_qty, section_id='stock'):
        self.check_stock_models(supply_point, product_id, expected_soh, expected_qty, section_id)


class CommTrackBalanceTransferTest(CommTrackSubmissionTest):

    def test_balance_submit(self):
        amounts = [(p._id, float(i*10)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_submission(amounts))
        for product, amt in amounts:
            self.check_product_stock(self.sp, product, amt, 0)

    def test_balance_enumerated(self):
        amounts = [(p._id, float(i*10)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_enumerated(amounts))
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

    def test_transfer_enumerated(self):
        initial = float(100)
        initial_amounts = [(p._id, initial) for p in self.products]
        self.submit_xml_form(balance_submission(initial_amounts))

        receipts = [(p._id, float(50 - 10*i)) for i, p in enumerate(self.products)]
        self.submit_xml_form(receipts_enumerated(receipts))
        for product, amt in receipts:
            self.check_product_stock(self.sp, product, initial + amt, amt)

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


class CommTrackSyncTest(CommTrackSubmissionTest):

    def setUp(self):
        super(CommTrackSyncTest, self).setUp()
        # reused stuff
        self.casexml_user = self.user.to_casexml_user()
        self.sp_block = CaseBlock(
            case_id=self.sp._id,
            version=V2,
        ).as_xml()

        # bootstrap ota stuff
        self.ct_settings.consumption_config = ConsumptionConfig(
            min_transactions=0,
            min_window=0,
            optimal_window=60,
        )
        self.ct_settings.ota_restore_config = StockRestoreConfig(
            section_to_consumption_types={'stock': 'consumption'}
        )
        set_default_consumption_for_domain(self.domain.name, 5)
        self.ota_settings = self.ct_settings.get_ota_restore_settings()

        # get initial restore token
        restore_config = RestoreConfig(
            self.casexml_user,
            version=V2,
            stock_settings=self.ota_settings,
        )
        self.sync_log_id = synclog_id_from_restore_payload(restore_config.get_payload())

    def testStockSyncToken(self):
        # first restore should not have the updated case
        check_user_has_case(self, self.casexml_user, self.sp_block, should_have=False,
                            restore_id=self.sync_log_id, version=V2)

        # submit with token
        amounts = [(p._id, float(i*10)) for i, p in enumerate(self.products)]
        self.submit_xml_form(balance_submission(amounts), last_sync_token=self.sync_log_id)
        # now restore should have the case
        check_user_has_case(self, self.casexml_user, self.sp_block, should_have=True,
                            restore_id=self.sync_log_id, version=V2, line_by_line=False)


def _report_soh(amounts, case_id, section_id='stock', report=None):
    if report is None:
        report = StockReport.objects.create(
            form_id=uuid.uuid4().hex,
            date=datetime.utcnow(),
            type=stockconst.REPORT_TYPE_BALANCE,
        )
    for product_id, amount in amounts:
        StockTransaction.objects.create(
            report=report,
            section_id=section_id,
            case_id=case_id,
            product_id=product_id,
            stock_on_hand=amount,
            quantity=0,
            type=stockconst.TRANSACTION_TYPE_STOCKONHAND,
        )
    return report
