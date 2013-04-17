from corehq.apps.commtrack.models import RequisitionCase
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.sms import handle
from casexml.apps.case.models import CommCareCase

class StockReportTest(CommTrackTest):

    def testStockReport(self):
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
        for code, amt in amounts.items():
            spp = CommCareCase.get(self.spps[code]._id)
            self.assertEqual(str(amt), spp.current_stock)

class StockRequisitionTest(CommTrackTest):
    requisitions_enabled = True

    def testRequisition(self):
        self.assertEqual(0, len(RequisitionCase.open_for_location(self.domain.name, self.loc._id)))

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

        # check updated status
        for code, amt in amounts.items():
            spp = CommCareCase.get(self.spps[code]._id)
            # make sure the index was created
            [req_ref] = spp.reverse_indices
            req_case = CommCareCase.get(req_ref.referenced_id)
            self.assertEqual(str(amt), req_case.amount_requested)
            self.assertEqual(req_case.location_, self.sp.location_)
            self.assertTrue(req_case._id in reqs)
