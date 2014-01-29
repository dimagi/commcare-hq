from corehq.apps.commtrack.models import CommtrackConfig, OpenLMISConfig
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.stockreport import Requisition
from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.commtrack.requisitions import create_requisition
from custom.openlmis.commtrack import requisition_receipt
from custom.openlmis.tests.mock_api import MockOpenLMISEndpoint


class ConfirmDeliveryTest(CommTrackTest):
    requisitions_enabled = True

    def setUp(self):
        super(ConfirmDeliveryTest, self).setUp()
        self.api = MockOpenLMISEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')

        openlmis_config = OpenLMISConfig()
        openlmis_config.enabled = True

        commtrack_config = CommtrackConfig.get(self.domain.commtrack_settings._id)
        commtrack_config.openlmis_config = openlmis_config
        commtrack_config.save()

    def testConfirmDelivery(self):
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
