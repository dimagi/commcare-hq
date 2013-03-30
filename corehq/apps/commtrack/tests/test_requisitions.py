from corehq.apps.commtrack.helpers import make_supply_point,\
    get_commtrack_user_id
from corehq.apps.commtrack import const
from corehq.apps.commtrack.tests.util import make_loc, TEST_DOMAIN,\
    CommTrackTest
from datetime import datetime
from corehq.apps.commtrack.stockreport import StockTransaction
from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.commtrack.requisitions import create_requisition

class RequisitionTest(CommTrackTest):
    requisitions_enabled = True

    def testMakeRequisition(self):
        config = self.domain.commtrack_settings
        for spp in self.spps.values():
            transaction = StockTransaction(
                config=config,
                user_id=self.user._id,
                product_id=spp.product,
                case_id=spp._id,
                action_name=config.get_action_by_type(RequisitionActions.REQUEST).action_name,
                value=20,
                inferred=False)
            req = create_requisition(spp, transaction)
            self.assertEqual("CommCareCase", req.doc_type)
            self.assertEqual(self.domain.name, req.domain)
            self.assertEqual(const.REQUISITION_CASE_TYPE, req.type)
            self.assertEqual(self.user._id, req.user_id)
            self.assertEqual(None, req.owner_id)
            self.assertFalse(req.closed)
            self.assertTrue(len(req.actions) > 0)
            [parent_ref] = req.indices
            self.assertEqual(const.PARENT_CASE_REF, parent_ref.identifier)
            self.assertEqual(const.SUPPLY_POINT_PRODUCT_CASE_TYPE, parent_ref.referenced_type)
            self.assertEqual(spp._id, parent_ref.referenced_id)
            self.assertEqual('20', req.amount_requested)
            for dateprop in ('opened_on', 'modified_on', 'server_modified_on'):
                self.assertTrue(getattr(req, dateprop) is not None)
                self.assertTrue(isinstance(getattr(req, dateprop), datetime))
