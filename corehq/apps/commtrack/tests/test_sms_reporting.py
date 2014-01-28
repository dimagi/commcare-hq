from datetime import datetime
from decimal import Decimal
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.const import RequisitionStatus
from corehq.apps.commtrack.models import RequisitionCase, SupplyPointProductCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.sms import handle, SMSError


class StockReportTest(CommTrackTest):

    def testStockReportRoaming(self):
        self.assertEqual(0, len(self.get_commtrack_forms()))
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.reporters['roaming'].get_verified_number(), 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        forms = list(self.get_commtrack_forms())
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        for code, amt in amounts.items():
            spp = SupplyPointProductCase.get(self.spps[code]._id)
            self.assertEqual(self.sp.location_, spp.location_)
            self.assertEqual(Decimal(amt), spp.current_stock)

        # todo: right now this makes one report per balance when really they should all be in the same one
        self.assertEqual(3, StockReport.objects.count())
        for report in StockReport.objects.all():
            self.assertEqual(forms[0]._id, report.form_id)
            self.assertEqual('balance', report.type)
            self.assertEqual(1, report.stocktransaction_set.count())

        for code, amt in amounts.items():
            [product] = filter(lambda p: p.code_ == code, self.products)
            trans = StockTransaction.objects.get(product_id=product._id)
            self.assertEqual(self.sp._id, trans.case_id)
            self.assertEqual(0, trans.quantity)
            self.assertEqual(amt, trans.stock_on_hand)


    def testStockReportFixed(self):
        self.assertEqual(0, len(self.get_commtrack_forms()))

        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.reporters['fixed'].get_verified_number(), 'soh {report}'.format(
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        forms = list(self.get_commtrack_forms())
        self.assertEqual(1, len(forms))
        self.assertEqual(_get_location_from_sp(self.sp), _get_location_from_form(forms[0]))

        for code, amt in amounts.items():
            spp = SupplyPointProductCase.get(self.spps[code]._id)
            self.assertEqual(self.sp.location_, spp.location_)
            self.assertEqual(Decimal(amt), spp.current_stock)


class StockRequisitionTest(object):
    requisitions_enabled = True

    def testRequisition(self):
        self.assertEqual(0, len(RequisitionCase.open_for_location(self.domain.name, self.loc._id)))
        self.assertEqual(0, len(self.get_commtrack_forms()))

        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # req loc1 pp 10 pq 20...
        handled = handle(self.user.get_verified_number(), 'req {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)

        # make sure we got the updated requisitions
        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)
        self.assertEqual(3, len(reqs))

        forms = list(self.get_commtrack_forms())
        self.assertEqual(1, len(forms))

        self.assertEqual(self.sp.location_, forms[0].location_)
        # check updated status
        for code, amt in amounts.items():
            spp = CommCareCase.get(self.spps[code]._id)
            # make sure the index was created
            [req_ref] = spp.reverse_indices
            req_case = RequisitionCase.get(req_ref.referenced_id)
            self.assertEqual(str(amt), req_case.amount_requested)
            self.assertEqual(self.user._id, req_case.requested_by)
            self.assertEqual(req_case.location_, self.sp.location_)
            self.assertTrue(req_case._id in reqs)
            self.assertEqual(spp._id, req_case.get_product_case()._id)

    def testApprovalBadLocations(self):
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

    def testSimpleApproval(self):
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

    def testSimplePack(self):
        self.testRequisition()

        # pack loc1
        handled = handle(self.user.get_verified_number(), 'pack {loc}'.format(
            loc='loc1',
        ))
        self.assertTrue(handled)
        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)
        self.assertEqual(3, len(reqs))

        for req_id in reqs:
            req_case = RequisitionCase.get(req_id)
            self.assertEqual(RequisitionStatus.PACKED, req_case.requisition_status)
            self.assertEqual(req_case.amount_requested, req_case.amount_packed)
            self.assertEqual(self.user._id, req_case.packed_by)
            self.assertIsNotNone(req_case.packed_on)
            self.assertTrue(isinstance(req_case.packed_on, datetime))
            self.assertEqual(req_case.product_id, req_case.get_product_case().product)

    def testReceipts(self):
        # this tests the requisition specific receipt keyword. not to be confused
        # with the standard stock receipt keyword
        self.testRequisition()

        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)
        self.assertEqual(3, len(reqs))
        req_ids_by_product_code = dict(((RequisitionCase.get(id).get_product().code, id) for id in reqs))

        rec_amounts = {
            'pp': 30,
            'pq': 20,
            'pr': 10,
        }
        # rec loc1 pp 10 pq 20...
        handled = handle(self.user.get_verified_number(), 'rec {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in rec_amounts.items())
        ))
        self.assertTrue(handled)

        # we should have closed the requisitions
        self.assertEqual(0, len(RequisitionCase.open_for_location(self.domain.name, self.loc._id)))

        forms = list(self.get_commtrack_forms())
        self.assertEqual(2, len(forms))

        self.assertEqual(self.sp.location_, forms[1].location_)
        # check updated status
        for code, amt in rec_amounts.items():
            req_case = RequisitionCase.get(req_ids_by_product_code[code])
            self.assertTrue(req_case.closed)
            self.assertEqual(str(amt), req_case.amount_received)
            self.assertEqual(self.user._id, req_case.received_by)
            self.assertTrue(req_case._id in reqs, 'requisition %s should be in %s' % (req_case._id, reqs))

    def testReceiptsWithNoOpenRequisition(self):
        # make sure we don't have any open requisitions
        self.assertEqual(0, len(RequisitionCase.open_for_location(self.domain.name, self.loc._id)))

        rec_amounts = {
            'pp': 30,
            'pq': 20,
            'pr': 10,
        }
        # rec loc1 pp 10 pq 20...
        handled = handle(self.user.get_verified_number(), 'rec {loc} {report}'.format(
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