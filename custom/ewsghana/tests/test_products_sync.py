import json
import os
from django.test import TestCase
from corehq.apps.commtrack.models import Product as Prod
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.programs.models import Program
from custom.ewsghana.api import Product, EWSApi
from custom.ewsghana.tests.mock_endpoint import MockEndpoint

TEST_DOMAIN = 'ewsghana-commtrack-product-test'


class ProductSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = EWSApi(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        for product in Prod.by_domain(TEST_DOMAIN):
            product.delete()

    def test_create_product(self):
        with open(os.path.join(self.datapath, 'sample_products.json')) as f:
            product = Product(json.loads(f.read())[0])
        self.assertEqual(0, len(Prod.by_domain(TEST_DOMAIN)))
        ewsghana_product = self.api_object.product_sync(product)
        self.assertEqual(product.sms_code, ewsghana_product.code.lower())
        self.assertEqual(product.name, ewsghana_product.name)
        self.assertEqual(product.description, ewsghana_product.description)
        self.assertEqual(product.units, str(ewsghana_product.unit))
        self.assertIsNotNone(ewsghana_product.program_id)
        program = Program.get(ewsghana_product.program_id)
        self.assertEqual(product.program.name, program.name)
        self.assertEqual(product.program.code, program.code)
