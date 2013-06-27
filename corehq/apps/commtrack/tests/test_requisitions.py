from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import SupplyPointProductCase
from corehq.apps.commtrack.tests.util import CommTrackTest
from datetime import datetime
from corehq.apps.commtrack.stockreport import Requisition
from corehq.apps.commtrack.const import RequisitionActions, RequisitionStatus
from corehq.apps.commtrack.requisitions import create_requisition

class RequisitionTest(CommTrackTest):
    requisitions_enabled = True

    def testMakeRequisition(self):
        config = self.domain.commtrack_settings
        for spp in self.spps.values():
            transaction = Requisition(
                config=config,
                product_id=spp.product,
                case_id=spp._id,
                action_name=config.get_action_by_type(RequisitionActions.REQUEST).action_name,
                value=20,
            )
            req = create_requisition(self.user._id, spp, transaction)
            self.assertEqual("CommCareCase", req.doc_type)
            self.assertEqual(spp.name, req.name)
            self.assertEqual(self.domain.name, req.domain)
            self.assertEqual(const.REQUISITION_CASE_TYPE, req.type)
            self.assertEqual(self.user._id, req.user_id)
            self.assertEqual(spp.owner_id, req.owner_id)
            self.assertFalse(req.closed)
            self.assertTrue(len(req.actions) > 0)
            self.assertEqual(req.location_, spp.location_)
            self.assertEqual(req.product_id, spp.product)

            [parent_ref] = req.indices
            self.assertEqual(const.PARENT_CASE_REF, parent_ref.identifier)
            self.assertEqual(const.SUPPLY_POINT_PRODUCT_CASE_TYPE, parent_ref.referenced_type)
            self.assertEqual(spp._id, parent_ref.referenced_id)
            self.assertEqual(spp._id, req.get_product_case()._id)
            self.assertTrue(isinstance(req.get_product_case(), SupplyPointProductCase))
            self.assertEqual(self.sp._id, req.get_supply_point_case()._id)
            self.assertEqual(RequisitionStatus.REQUESTED, req.requisition_status)
            self.assertEqual('20', req.amount_requested)
            self.assertEqual(self.user._id, req.requested_by)
            for dateprop in ('opened_on', 'modified_on', 'server_modified_on'):
                self.assertTrue(getattr(req, dateprop) is not None)
                self.assertTrue(isinstance(getattr(req, dateprop), datetime))
