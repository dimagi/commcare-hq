from datetime import datetime
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import RequisitionCase, StockState
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.tests.util import CommTrackTest, bootstrap_user, FIXED_USER, ROAMING_USER
from corehq.apps.commtrack.sms import handle, SMSError


class SMSTests(CommTrackTest):
    def setUp(self):
        super(SMSTests, self).setUp()

    def check_stock(self, code, amount, case_id=None, section_id='stock'):
        if not case_id:
            case_id = self.sp._id

        [product] = filter(lambda p: p.code_ == code, self.products)

        try:
            state = StockState.objects.get(
                product_id=product._id,
                case_id=case_id,
                section_id=section_id
            )
            self.assertEqual(amount, state.stock_on_hand)
        except StockState.DoesNotExist:
            if amount != 0:
                # only error if we weren't checking for no stock
                raise Exception(
                    'StockState for "%s" section does not exist' % section_id
                )


class StockReportTest(SMSTests):
    user_definitions = [ROAMING_USER, FIXED_USER]

    def testStockReportRoaming(self):
        self.assertEqual(0, len(self.get_commtrack_forms(self.domain.name)))
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        forms = list(self.get_commtrack_forms(self.domain.name))
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        self.assertEqual(1, StockReport.objects.count())
        report = StockReport.objects.all()[0]
        self.assertEqual(forms[0]._id, report.form_id)
        self.assertEqual('balance', report.type)
        self.assertEqual(3, report.stocktransaction_set.count())

        for code, amt in amounts.items():
            [product] = filter(lambda p: p.code_ == code, self.products)
            trans = StockTransaction.objects.get(product_id=product._id)
            self.assertEqual(self.sp._id, trans.case_id)
            self.assertEqual(0, trans.quantity)
            self.assertEqual(amt, trans.stock_on_hand)

    def testStockReportFixed(self):
        self.assertEqual(0, len(self.get_commtrack_forms(self.domain.name)))

        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.users[1].get_verified_number(), 'soh {report}'.format(
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        forms = list(self.get_commtrack_forms(self.domain.name))
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        for code, amt in amounts.items():
            [product] = filter(lambda p: p.code_ == code, self.products)
            trans = StockTransaction.objects.get(product_id=product._id)
            self.assertEqual(self.sp._id, trans.case_id)
            self.assertEqual(0, trans.quantity)
            self.assertEqual(amt, trans.stock_on_hand)

    def check_form_type(self, expected_type, subtype=None):
        [report] = StockReport.objects.filter(type='transfer')
        transaction = report.stocktransaction_set.all()[0]
        self.assertEqual(
            transaction.type,
            expected_type
        )
        if subtype:
            self.assertEqual(
                transaction.subtype,
                subtype
            )

    def testStockReceipt(self):
        original_amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # First submit an soh so we can make sure receipts functions
        # differently than soh
        handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ))

        received_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(self.users[0].get_verified_number(), 'r {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in received_amounts.items())
        ))

        self.assertTrue(handled)

        self.check_form_type('receipts')

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] + received_amounts[code]
            self.check_stock(code, expected_amount)

    def testStockLosses(self):
        original_amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # First submit an soh so we can make sure losses functions properly
        handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ))

        lost_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(self.users[0].get_verified_number(), 'l {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ))

        self.assertTrue(handled)

        self.check_form_type('consumption', 'loss')

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] - lost_amounts[code]
            self.check_stock(code, expected_amount)

    def testStockConsumption(self):
        original_amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # First submit an soh so we can make sure consumption functions properly
        handle(self.users[0].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in original_amounts.items())
        ))

        lost_amounts = {
            'pp': 1,
            'pq': 2,
            'pr': 3,
        }

        handled = handle(self.users[0].get_verified_number(), 'c {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in lost_amounts.items())
        ))

        self.assertTrue(handled)

        # this is the only difference from losses..
        self.check_form_type('consumption')

        for code in original_amounts.keys():
            expected_amount = original_amounts[code] - lost_amounts[code]
            self.check_stock(code, expected_amount)


class StockRequisitionTest(SMSTests):
    requisitions_enabled = True
    user_definitions = [ROAMING_USER]

    def testRequisition(self):
        # confirm we have a clean start
        self.assertEqual(0, len(RequisitionCase.open_for_location(self.domain.name, self.loc._id)))
        self.assertEqual(0, len(self.get_commtrack_forms(self.domain.name)))

        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # req loc1 pp 10 pq 20...
        handled = handle(self.users[0].get_verified_number(), 'req {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))

        self.assertTrue(handled)

        # make sure we got the updated requisitions
        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)
        self.assertEqual(1, len(reqs))

        req = RequisitionCase.get(reqs[0])
        [index] = req.indices

        self.assertEqual(req.requisition_status, 'requested')
        self.assertEqual(const.SUPPLY_POINT_CASE_TYPE, index.referenced_type)
        self.assertEqual(self.sp._id, index.referenced_id)
        self.assertEqual('parent_id', index.identifier)

        # check updated status
        for code, amt in amounts.items():
            self.check_stock(code, amt, req._id, 'ct-requested')
            self.check_stock(code, 0, req._id, 'stock')

    def inactive_testApprovalBadLocations(self):
        self.testRequisition()

        try:
            handle(self.user.get_verified_number(), 'approve')
            self.fail("empty locations should fail")
        except SMSError, e:
            self.assertEqual('must specify a location code', str(e))

        try:
            handle(self.user.get_verified_number(), 'approve notareallocation')
            self.fail("unknown locations should fail")
        except SMSError, e:
            self.assertTrue('invalid location code' in str(e))

    def inactive_testSimpleApproval(self):
        self.testRequisition()

        # approve loc1
        handled = handle(self.user.get_verified_number(), 'approve {loc}'.format(
            loc='loc1',
            ))
        self.assertTrue(handled)
        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)
        self.assertEqual(3, len(reqs))

        for req_id in reqs:
            req_case = RequisitionCase.get(req_id)
            self.assertEqual(RequisitionStatus.APPROVED, req_case.requisition_status)
            self.assertEqual(req_case.amount_requested, req_case.amount_approved)
            self.assertEqual(self.user._id, req_case.approved_by)
            self.assertIsNotNone(req_case.approved_on)
            self.assertTrue(isinstance(req_case.approved_on, datetime))
            self.assertEqual(req_case.product_id, req_case.get_product_case().product)

    def testSimpleFulfill(self):
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # start with an open request
        handle(
            self.users[0].get_verified_number(),
            'req {loc} {report}'.format(
                loc='loc1',
                report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
            )
        )

        # fulfill loc1
        handled = handle(
            self.users[0].get_verified_number(),
            'fulfill {loc} {report}'.format(
                loc='loc1',
                report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
            )
        )
        self.assertTrue(handled)

        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)

        # should not have created a new req
        self.assertEqual(1, len(reqs))

        req = RequisitionCase.get(reqs[0])
        [index] = req.indices

        self.assertEqual(req.requisition_status, 'fulfilled')

        for code, amt in amounts.items():
            self.check_stock(code, amt, req._id, 'stock')
            self.check_stock(code, amt, req._id, 'ct-fulfilled')

    def testReceipt(self):
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }

        # start with an open request
        handle(
            self.users[0].get_verified_number(),
            'req {loc} {report}'.format(
                loc='loc1',
                report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
            )
        )

        # fulfill it
        handle(
            self.users[0].get_verified_number(),
            'fulfill {loc} {report}'.format(
                loc='loc1',
                report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
            )
        )

        # grab this first because we are about to close it
        req_id = RequisitionCase.open_for_location(self.domain.name, self.loc._id)[0]

        # mark it received
        handle(
            self.users[0].get_verified_number(),
            'rec {loc} {report}'.format(
                loc='loc1',
                report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
            )
        )

        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)

        # receiving by sms closes the req
        self.assertEqual(0, len(reqs))

        req = RequisitionCase.get(req_id)
        [index] = req.indices

        self.assertEqual(req.requisition_status, 'received')

        # check updated status
        for code, amt in amounts.items():
            self.check_stock(code, 0, req._id, 'stock')
            self.check_stock(code, amt, self.sp._id, 'stock')
            # TODO some day we will track this too
            # self.check_stock(code, amt, req._id, 'ct-received')

    def testReceiptsWithNoOpenRequisition(self):
        # TODO what should actually happen in this case?

        # make sure we don't have any open requisitions
        self.assertEqual(0, len(RequisitionCase.open_for_location(self.domain.name, self.loc._id)))

        rec_amounts = {
            'pp': 30,
            'pq': 20,
            'pr': 10,
        }
        # rec loc1 pp 10 pq 20...
        handled = handle(self.users[0].get_verified_number(), 'rec {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in rec_amounts.items())
        ))
        self.assertTrue(handled)

        # should still be no open requisitions
        self.assertEqual(0, len(RequisitionCase.open_for_location(self.domain.name, self.loc._id)))


def _get_location_from_form(form):
    return form.form['location']

def _get_location_from_sp(sp):
    return sp.location_[-1]
