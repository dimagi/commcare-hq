from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import SupplyPointProductCase, Product, Program, CommtrackConfig, OpenLMISConfig
from corehq.apps.commtrack.tests.util import CommTrackTest, bootstrap_domain, TEST_DOMAIN
from datetime import datetime
from corehq.apps.commtrack.stockreport import Requisition
from corehq.apps.commtrack.const import RequisitionActions, RequisitionStatus
from corehq.apps.commtrack.requisitions import create_requisition
from custom.openlmis.signals import stock_data_submission
from corehq.apps.commtrack.helpers import make_supply_point,\
    make_supply_point_product
from custom.openlmis.tests.mock_api import MockOpenLMISEndpoint, MockOpenLMISSubmitEndpoint


class SignalsTest(CommTrackTest):
    requisitions_enabled = True
    program = None

    def createProgram(self):
        self.program = Program()
        self.program.domain = TEST_DOMAIN
        self.program.code = 'QYZ'
        self.program.name = "hiv_program"

        self.program.save()

    def createProducts(self):

        product_1_dict = {
            'domain': TEST_DOMAIN,
            'code':'123',
            'name':'hiv',
            'description':'desc1',
            'category':'test_category',
            'program_id': self.program._id,
            "beginningBalance":'3',
            "quantityReceived":'0',
            "quantityDispensed":'1',
            "lossesAndAdjustments":'-2',
            "stockOnHand":'0',
            "newPatientCount":'2',
            "stockOutDays":'2',
            "quantityRequested":'3',
            "reasonForRequestedQuantity":"reason",
            "calculatedOrderQuantity":'57',
            "quantityApproved":'65',
            "remarks":"1"
        }
        product_2_dict = {
            'domain': TEST_DOMAIN,
            'code':'234',
            'name':'asd',
            'description':'desc2',
            'category':'test_category',
            'program_id': self.program._id,
            "beginningBalance":'3',
            "quantityReceived":'0',
            "quantityDispensed":'1',
            "lossesAndAdjustments":'-2',
            "stockOnHand":'0',
            "newPatientCount":'2',
            "stockOutDays":'2',
            "quantityRequested":'3',
            "reasonForRequestedQuantity":"reason",
            "calculatedOrderQuantity":'57',
            "quantityApproved":'65',
            "remarks":"1"
        }
        product_1 = Product(product_1_dict)
        product_2 = Product(product_2_dict)
        product_1.save()
        product_2.save()

        self.products = []
        self.products.append(product_1)
        self.products.append(product_2)

    def setUp(self):
        super(SignalsTest, self).setUp()
        self.spps.clear()

        self.createProgram()
        self.createProducts()

        openlmis_config = OpenLMISConfig()
        openlmis_config.enabled = True

        commtrack_config = CommtrackConfig.get(self.domain.commtrack_settings._id)
        commtrack_config.openlmis_config = openlmis_config
        commtrack_config.save()

        for p in self.products:
            self.spps[p.code] = make_supply_point_product(self.sp, p._id)

    def testSyncStockRequisition(self):
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
        endpoint = MockOpenLMISSubmitEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')
        stock_data_submission(sender=None, requisition_cases=requisition_cases, endpoint=endpoint)

        for req in requisition_cases:
            self.assertEqual(req.external_id, 'REQ_123')