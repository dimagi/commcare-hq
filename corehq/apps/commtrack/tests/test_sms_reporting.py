from datetime import datetime
from corehq.apps.commtrack.const import RequisitionStatus
from corehq.apps.commtrack.models import RequisitionCase
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.sms import handle
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance


class StockReportTest(CommTrackTest):

    def testStockReport(self):
        self.assertEqual(0, len(self.get_commtrack_forms()))

        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.verified_number, 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        forms = list(self.get_commtrack_forms())
        self.assertEqual(1, len(forms))
        self.assertEqual(self.sp.location_, forms[0].location_)

        for code, amt in amounts.items():
            spp = CommCareCase.get(self.spps[code]._id)
            self.assertEqual(self.sp.location_, spp.location_)
            self.assertEqual(str(amt), spp.current_stock)

class StockRequisitionTest(CommTrackTest):
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
        handled = handle(self.verified_number, 'req {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)

        # make sure we got the updated requisitions
        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)
        self.assertEqual(3, len(reqs))

        forms = list(self.get_commtrack_forms())
        self.assertEqual(1, len(forms))

        # todo: should this be the case? need to investigate further
        # self.assertEqual(self.sp.location_, forms[0].location_)
        # check updated status
        for code, amt in amounts.items():
            spp = CommCareCase.get(self.spps[code]._id)
            # make sure the index was created
            [req_ref] = spp.reverse_indices
            req_case = CommCareCase.get(req_ref.referenced_id)
            self.assertEqual(str(amt), req_case.amount_requested)
            self.assertEqual(req_case.location_, self.sp.location_)
            self.assertTrue(req_case._id in reqs)

    def testSimpleApproval(self):
        self.testRequisition()

        # req loc1 pp 10 pq 20...
        handled = handle(self.verified_number, 'approve {loc}'.format(
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

    def testSimpleFill(self):
        self.testRequisition()

        # req loc1 pp 10 pq 20...
        handled = handle(self.verified_number, 'fill {loc}'.format(
            loc='loc1',
        ))
        self.assertTrue(handled)
        reqs = RequisitionCase.open_for_location(self.domain.name, self.loc._id)
        self.assertEqual(3, len(reqs))

        for req_id in reqs:
            req_case = RequisitionCase.get(req_id)
            self.assertEqual(RequisitionStatus.FILLED, req_case.requisition_status)
            self.assertEqual(req_case.amount_requested, req_case.amount_filled)
            self.assertEqual(self.user._id, req_case.filled_by)
            self.assertIsNotNone(req_case.filled_on)
            self.assertTrue(isinstance(req_case.filled_on, datetime))
