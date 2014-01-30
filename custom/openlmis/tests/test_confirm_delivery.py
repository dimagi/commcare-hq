from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.commtrack.requisitions import create_requisition
from custom.openlmis.commtrack import requisition_receipt
from custom.openlmis.tests.base import OpenLMISTestBase

class ConfirmDeliveryTest(OpenLMISTestBase):

    def fixmetestConfirmDelivery(self):
        from corehq.apps.commtrack.stockreport import Requisition
        requisition_cases = []
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
            requisition_cases.append(req)
        self.assertTrue(requisition_receipt.send(sender=None, requisitions=requisition_cases))
