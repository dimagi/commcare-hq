import json
import os
from django.test import TestCase
from corehq.apps.commtrack.models import Product as Prod
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from custom.ilsgateway.api import Product
from custom.ilsgateway.commtrack import sync_ilsgateway_product

TEST_DOMAIN = 'ilsgateway-commtrack-product-test'


class ProductSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        for product in Prod.by_domain(TEST_DOMAIN):
            product.delete()

    def test_create_product(self):
        with open(os.path.join(self.datapath, 'sample_product.json')) as f:
            product = Product.from_json(json.loads(f.read()))
        self.assertEqual(0, len(Prod.by_domain(TEST_DOMAIN)))
        ilsgateway_product = sync_ilsgateway_product(TEST_DOMAIN, product)
        self.assertEqual(product.sms_code, ilsgateway_product.code.lower())
        self.assertEqual(product.name, ilsgateway_product.name)
        self.assertEqual(product.description, ilsgateway_product.description)
        self.assertEqual(product.units, str(ilsgateway_product.unit))

