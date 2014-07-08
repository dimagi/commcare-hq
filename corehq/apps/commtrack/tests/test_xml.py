from decimal import Decimal
from lxml import etree
import os
import random
import uuid
from datetime import datetime
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreConfig
from casexml.apps.phone.tests.utils import synclog_id_from_restore_payload
from corehq.apps.commtrack.models import ConsumptionConfig, StockRestoreConfig, RequisitionCase, Product, StockState
from corehq.apps.consumption.shortcuts import set_default_monthly_consumption_for_domain
from couchforms.models import XFormInstance
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.stock import const as stockconst
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack import const
from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml, FIXED_USER, extract_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line, check_user_has_case
from corehq.apps.hqcase.utils import get_cases_in_domain
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.commtrack.tests.util import make_loc, make_supply_point
from corehq.apps.commtrack.const import DAYS_IN_MONTH
from corehq.apps.commtrack.requisitions import get_notification_message
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
    create_received_xml,
    receipts_enumerated,
    balance_enumerated,
    products_xml, long_date)


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
        set_default_monthly_consumption_for_domain(self.domain.name, 5 * DAYS_IN_MONTH)

        amounts = [(p._id, i*10) for i, p in enumerate(self.products)]
        report = _report_soh(amounts, self.sp._id, 'stock')
        balance_blocks = _get_ota_balance_blocks(self.ct_settings, self.user)
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
                [(p._id, 150) for p in self.products],
                datestring=json_format_datetime(report.date),
            ),
             consumption_block,
        )

    def test_force_consumption(self):
        self.ct_settings.consumption_config = ConsumptionConfig(
            min_transactions=0,
            min_window=0,
            optimal_window=60,
        )
        self.ct_settings.ota_restore_config = StockRestoreConfig(
            section_to_consumption_types={'stock': 'consumption'},
        )
        set_default_monthly_consumption_for_domain(self.domain.name, 5)

        balance_blocks = _get_ota_balance_blocks(self.ct_settings, self.user)
        self.assertEqual(0, len(balance_blocks))

        # self.ct_settings.ota_restore_config.use_dynamic_product_list = True
        self.ct_settings.ota_restore_config.force_consumption_case_types = [const.SUPPLY_POINT_CASE_TYPE]
        balance_blocks = _get_ota_balance_blocks(self.ct_settings, self.user)
        self.assertEqual(1, len(balance_blocks))
        [balance_block] = balance_blocks
        element = etree.fromstring(balance_block)
        self.assertEqual(0, len([child for child in element]))

        self.ct_settings.ota_restore_config.use_dynamic_product_list = True
        balance_blocks = _get_ota_balance_blocks(self.ct_settings, self.user)
        self.assertEqual(1, len(balance_blocks))
        [balance_block] = balance_blocks
        element = etree.fromstring(balance_block)
        self.assertEqual(3, len([child for child in element]))


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
        instance_id = uuid.uuid4().hex
        instance = submission_wrap(
            instance_id,
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
        return instance_id

    def check_stock_models(self, case, product_id, expected_soh, expected_qty, section_id):
        if not isinstance(expected_qty, Decimal):
            expected_qty = Decimal(str(expected_qty))
        if not isinstance(expected_soh, Decimal):
            expected_soh = Decimal(str(expected_soh))

        latest_trans = StockTransaction.latest(case._id, section_id, product_id)
        self.assertIsNotNone(latest_trans)
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
            self.assertEqual(Decimal(str(inferred)), inferred_txn.quantity)
            self.assertEqual(Decimal(str(amt)), inferred_txn.stock_on_hand)
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


class BugSubmissionsTest(CommTrackSubmissionTest):
    def test_device_report_submissions_ignored(self):
        """
        submit a device report with a stock block and make sure it doesn't
        get processed
        """
        self.assertEqual(0, StockTransaction.objects.count())

        fpath = os.path.join(os.path.dirname(__file__), 'data', 'xml', 'device_log.xml')
        with open(fpath) as f:
            form = f.read()
        amounts = [(p._id, 10) for p in self.products]
        product_block = products_xml(amounts)
        form = form.format(
            form_id=uuid.uuid4().hex,
            user_id=self.user._id,
            date=long_date(),
            sp_id=self.sp._id,
            product_block=product_block
        )
        submit_form_locally(
            instance=form,
            domain=self.domain.name,
        )
        self.assertEqual(0, StockTransaction.objects.count())


class CommTrackRequisitionTest(CommTrackSubmissionTest):

    def setUp(self):
        self.requisitions_enabled = True
        super(CommTrackRequisitionTest, self).setUp()

    def expected_notification_message(self, req, amounts):
        summary = sorted(
            ['%s:%d' % (str(Product.get(p).code), amt) for p, amt in amounts]
        )
        return const.notification_template(req.get_next_action().action).format(
            name='Unknown',  # TODO currently not storing requester
            summary=' '.join(summary),
            loc=self.sp.location.site_code,
            keyword=req.get_next_action().keyword
        )

    def test_create_fulfill_and_receive_requisition(self):
        amounts = [(p._id, 50.0 + float(i*10)) for i, p in enumerate(self.products)]

        # ----------------
        # Create a request
        # ----------------

        self.submit_xml_form(create_requisition_xml(amounts))
        req_cases = list(get_cases_in_domain(self.domain.name, type=const.REQUISITION_CASE_TYPE))
        self.assertEqual(1, len(req_cases))
        req = RequisitionCase.get(req_cases[0]._id)
        [index] = req.indices

        self.assertEqual(req.requisition_status, 'requested')
        self.assertEqual(const.SUPPLY_POINT_CASE_TYPE, index.referenced_type)
        self.assertEqual(self.sp._id, index.referenced_id)
        self.assertEqual('parent_id', index.identifier)
        # TODO: these types of tests probably belong elsewhere
        self.assertEqual(req.get_next_action().keyword, 'fulfill')
        self.assertEqual(req.get_location()._id, self.sp.location._id)
        self.assertEqual(len(RequisitionCase.open_for_location(
            self.domain.name,
            self.sp.location._id
        )), 1)
        self.assertEqual(
            get_notification_message(
                req.get_next_action(),
                [req]
            ),
            self.expected_notification_message(req, amounts)
        )

        for product, amt in amounts:
            self.check_stock_models(req, product, amt, 0, 'ct-requested')

        # ----------------
        # Mark it fulfilled
        # -----------------

        self.submit_xml_form(create_fulfillment_xml(req, amounts))

        req = RequisitionCase.get(req._id)

        self.assertEqual(req.requisition_status, 'fulfilled')
        self.assertEqual(req.get_next_action().keyword, 'rec')
        self.assertEqual(
            get_notification_message(
                req.get_next_action(),
                [req]
            ),
            self.expected_notification_message(req, amounts)
        )

        for product, amt in amounts:
            # we are expecting two separate blocks to have come with the same
            # values
            self.check_stock_models(req, product, amt, amt, 'stock')
            self.check_stock_models(req, product, amt, 0, 'ct-fulfilled')

        # ----------------
        # Mark it received
        # ----------------

        self.submit_xml_form(create_received_xml(req, amounts))

        req = RequisitionCase.get(req._id)

        self.assertEqual(req.requisition_status, 'received')
        self.assertIsNone(req.get_next_action())
        self.assertEqual(len(RequisitionCase.open_for_location(
            self.domain.name,
            self.sp.location._id
        )), 0)

        for product, amt in amounts:
            self.check_stock_models(req, product, 0, -amt, 'stock')
            self.check_stock_models(self.sp, product, amt, amt, 'stock')


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
        set_default_monthly_consumption_for_domain(self.domain.name, 5)
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


class CommTrackArchiveSubmissionTest(CommTrackSubmissionTest):

    def testArchiveLastForm(self):
        initial_amounts = [(p._id, float(100)) for p in self.products]
        self.submit_xml_form(balance_submission(initial_amounts))

        final_amounts = [(p._id, float(50)) for i, p in enumerate(self.products)]
        second_form_id = self.submit_xml_form(balance_submission(final_amounts))

        def _assert_initial_state():
            self.assertEqual(1, StockReport.objects.filter(form_id=second_form_id).count())
            # 6 = 3 stockonhand and 3 inferred consumption txns
            self.assertEqual(6, StockTransaction.objects.filter(report__form_id=second_form_id).count())
            self.assertEqual(3, StockState.objects.filter(case_id=self.sp._id).count())
            for state in StockState.objects.filter(case_id=self.sp._id):
                self.assertEqual(Decimal(50), state.stock_on_hand)
                self.assertIsNotNone(state.daily_consumption)

        # check initial setup
        _assert_initial_state()

        # archive and confirm commtrack data is deleted
        form = XFormInstance.get(second_form_id)
        form.archive()
        self.assertEqual(0, StockReport.objects.filter(form_id=second_form_id).count())
        self.assertEqual(0, StockTransaction.objects.filter(report__form_id=second_form_id).count())
        self.assertEqual(3, StockState.objects.filter(case_id=self.sp._id).count())
        for state in StockState.objects.filter(case_id=self.sp._id):
            # balance should be reverted to 100 in the StockState
            self.assertEqual(Decimal(100), state.stock_on_hand)
            # consumption should be none since there will only be 1 data point
            self.assertIsNone(state.daily_consumption)

        # unarchive and confirm commtrack data is restored
        form.unarchive()
        _assert_initial_state()

    def testArchiveOnlyForm(self):
        # check no data in stock states
        self.assertEqual(0, StockState.objects.filter(case_id=self.sp._id).count())

        initial_amounts = [(p._id, float(100)) for p in self.products]
        form_id = self.submit_xml_form(balance_submission(initial_amounts))

        # check that we made stuff
        def _assert_initial_state():
            self.assertEqual(1, StockReport.objects.filter(form_id=form_id).count())
            self.assertEqual(3, StockTransaction.objects.filter(report__form_id=form_id).count())
            self.assertEqual(3, StockState.objects.filter(case_id=self.sp._id).count())
            for state in StockState.objects.filter(case_id=self.sp._id):
                self.assertEqual(Decimal(100), state.stock_on_hand)
        _assert_initial_state()

        # archive and confirm commtrack data is cleared
        form = XFormInstance.get(form_id)
        form.archive()
        self.assertEqual(0, StockReport.objects.filter(form_id=form_id).count())
        self.assertEqual(0, StockTransaction.objects.filter(report__form_id=form_id).count())
        self.assertEqual(0, StockState.objects.filter(case_id=self.sp._id).count())

        # unarchive and confirm commtrack data is restored
        form.unarchive()
        _assert_initial_state()


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

def _get_ota_balance_blocks(ct_settings, user):
    ota_settings = ct_settings.get_ota_restore_settings()
    restore_config = RestoreConfig(
        user.to_casexml_user(),
        version=V2,
        stock_settings=ota_settings,
    )
    return extract_balance_xml(restore_config.get_payload())
