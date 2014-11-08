import os
import json
from django.test import TestCase
from casexml.apps.case.tests import delete_all_cases
from corehq.apps.commtrack.models import RequisitionCase
from corehq.apps.products.models import Product
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from custom.openlmis.api import Program, Product as LMISProduct
from custom.openlmis.commtrack import bootstrap_domain, sync_openlmis_program, sync_openlmis_product, sync_requisition_from_openlmis
from custom.openlmis.tests import MockOpenLMISEndpoint

TEST_DOMAIN = 'openlmis-commtrack-program-test'

class RequisitionSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        self.api = MockOpenLMISEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')
        initial_bootstrap(TEST_DOMAIN)
        bootstrap_domain(TEST_DOMAIN)
        delete_all_cases()
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()

    def fixmetestSyncRequisition(self):
        with open(os.path.join(self.datapath, 'sample_program.json')) as f:
            lmis_program = Program.from_json(json.loads(f.read()))
        commtrack_program = sync_openlmis_program(TEST_DOMAIN, lmis_program)
        test_product = LMISProduct.from_json({
            "programCode": "ESS_MEDS",
            "programName": "ESSENTIAL MEDICINES",
            "productCode": "P26",
            "productName": "Erythromycin ethyl succinate, pwd oral suspension, 125mg/5ml",
            "description": "TDF/FTC/EFV",
            "unit": 10,
            "category": "Analgesics"
        })
        sync_openlmis_product(TEST_DOMAIN, commtrack_program, test_product)
        sync_requisition_from_openlmis(TEST_DOMAIN, 1, self.api)
        self.assertTrue(1, len(RequisitionCase.get_by_external(TEST_DOMAIN, 1)))
