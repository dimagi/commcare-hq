import json
from corehq.apps.commtrack.models import CommtrackConfig, OpenLMISConfig
from corehq.apps.programs.models import Program
from corehq.apps.products.models import Product
from corehq.apps.commtrack.tests.util import TEST_DOMAIN
from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.commtrack.requisitions import create_requisition
from custom.openlmis.signals import stock_data_submission
from custom.openlmis.tests.base import OpenLMISTestBase
from custom.openlmis.tests.mock_api import MockOpenLMISSubmitEndpoint
import os

class SignalsTest(OpenLMISTestBase):
    requisitions_enabled = True
    program = None

    def createProgram(self):
        self.program = Program()
        self.program.domain = TEST_DOMAIN
        self.program.code = 'QYZ'
        self.program.name = "hiv_program"

        self.program.save()

    def createProducts(self):
        with open(os.path.join(self.datapath, 'sample_product_1.json')) as f:
            lmis_product_1 = json.loads(f.read())

        with open(os.path.join(self.datapath, 'sample_product_2.json')) as f:
            lmis_product_2 = json.loads(f.read())

        lmis_product_1['program_id'] =  self.program._id
        lmis_product_2['program_id'] =  self.program._id

        product_1 = Product(lmis_product_1)
        product_2 = Product(lmis_product_2)
        product_1.save()
        product_2.save()

        self.products = []
        self.products.append(product_1)
        self.products.append(product_2)

    def setUp(self):
        super(SignalsTest, self).setUp()
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        self.spps.clear()
        self.createProgram()
        self.createProducts()

    def fixmetestSyncStockRequisition(self):
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
        endpoint = MockOpenLMISSubmitEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')
        stock_data_submission(sender=None, cases=requisition_cases, endpoint=endpoint)

        for req in requisition_cases:
            self.assertEqual(req.external_id, 'REQ_123')
