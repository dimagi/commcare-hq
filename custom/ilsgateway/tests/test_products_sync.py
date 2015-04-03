from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.models import Product as Prod
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from custom.ilsgateway.api import Product, ILSGatewayAPI
from custom.logistics.commtrack import synchronization
from custom.logistics.models import MigrationCheckpoint
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint

TEST_DOMAIN = 'ilsgateway-commtrack-product-test'


class ProductSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = ILSGatewayAPI(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        for product in Prod.by_domain(TEST_DOMAIN):
            product.delete()

    def test_create_product(self):
        with open(os.path.join(self.datapath, 'sample_products.json')) as f:
            product = Product(json.loads(f.read())[0])
        self.assertEqual(0, len(Prod.by_domain(TEST_DOMAIN)))
        ilsgateway_product = self.api_object.product_sync(product)
        self.assertEqual(product.sms_code, ilsgateway_product.code.lower())
        self.assertEqual(product.name, ilsgateway_product.name)
        self.assertEqual(product.description, ilsgateway_product.description)
        self.assertEqual(product.units, str(ilsgateway_product.unit))

    def test_locations_migration(self):
        checkpoint = MigrationCheckpoint(
            domain=TEST_DOMAIN,
            start_date=datetime.utcnow(),
            date=datetime.utcnow(),
            api='product',
            limit=100,
            offset=0
        )
        synchronization('product',
                        self.endpoint.get_products,
                        self.api_object.product_sync, checkpoint, None, 100, 0)
        self.assertEqual('product', checkpoint.api)
        self.assertEqual(100, checkpoint.limit)
        self.assertEqual(0, checkpoint.offset)
        self.assertEqual(6, len(list(Prod.by_domain(TEST_DOMAIN))))
