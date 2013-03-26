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
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.verified_number, 'req {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        for code, amt in amounts.items():
            spp = CommCareCase.get(self.spps[code]._id)
            # make sure the index was created
            [req_ref] = spp.reverse_indices
            req_case = CommCareCase.get(req_ref.referenced_id)
            self.assertEqual(str(amt), req_case.amount_requested)
