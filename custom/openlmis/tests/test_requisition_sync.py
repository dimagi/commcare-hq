import os
import json
from django.test import TestCase
from casexml.apps.case.tests import delete_all_cases
from corehq.apps.commtrack.models import Product, RequisitionCase
from custom.openlmis.api import Program
from custom.openlmis.commtrack import bootstrap_domain, sync_openlmis_program, sync_openlmis_product, sync_requisition_from_openlmis
from custom.openlmis.tests import MockOpenLMISEndpoint

TEST_DOMAIN = 'openlmis-commtrack-program-test'

class RequisitionSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        self.api = MockOpenLMISEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')
        bootstrap_domain(TEST_DOMAIN)
        delete_all_cases()
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()

    def testSyncRequisition(self):
        with open(os.path.join(self.datapath, 'sample_program.json')) as f:
            lmis_program = Program.from_json(json.loads(f.read()))
        commtrack_program = sync_openlmis_program(TEST_DOMAIN, lmis_program)
        test_product = {
            'name': 'Test',
            'code': 'P151',
            'unit': 10,
            'description': 'decs',
            'category': 'category',
        }
        sync_openlmis_product(TEST_DOMAIN, commtrack_program, test_product)
        sync_requisition_from_openlmis(TEST_DOMAIN, 1, self.api)
        self.assertTrue(1, len(RequisitionCase.get_by_external(TEST_DOMAIN, 1)))