import json
import os
from django.test import TestCase
from corehq.apps.products.models import Product
from custom.openlmis.api import Program
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from custom.openlmis.commtrack import sync_openlmis_program, bootstrap_domain

TEST_DOMAIN = 'openlmis-commtrack-program-test'


class ProgramSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        bootstrap_domain(TEST_DOMAIN)
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()

    def testCreateProgram(self):
        with open(os.path.join(self.datapath, 'sample_program.json')) as f:
            lmis_program = Program.from_json(json.loads(f.read()))

        # program sync
        self.assertEqual(0, len(Product.by_domain(TEST_DOMAIN)))
        commtrack_program = sync_openlmis_program(TEST_DOMAIN, lmis_program)
        self.assertEqual(lmis_program.name, commtrack_program.name)
        self.assertEqual(lmis_program.code.lower(), commtrack_program.code)

        # product sync
        self.assertEqual(len(lmis_program.products), len(Product.by_domain(TEST_DOMAIN)))
        lmis_product = lmis_program.products[0]
        product = Product.get_by_code(TEST_DOMAIN, lmis_product.code)
        self.assertEqual(product.code, lmis_product.code.lower())
        self.assertEqual(product.name, lmis_product.name)
        self.assertEqual(product.description, lmis_product.description)
        self.assertEqual(product.unit, str(lmis_product.unit))
        self.assertEqual(product.category, str(lmis_product.category))
