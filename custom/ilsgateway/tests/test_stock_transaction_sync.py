import json
import os
import datetime
from django.test.testcases import TestCase
from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from custom.ilsgateway.api import ILSGatewayAPI, Product
from custom.ilsgateway.models import ILSGatewayConfig, SupplyPointStatus, DeliveryGroupReport
from custom.ilsgateway.stock_data import ILSStockDataSynchronization
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from custom.logistics.models import StockDataCheckpoint
from custom.logistics.tasks import stock_data_task
from corehq.apps.commtrack.models import SupplyPointCase, StockState


TEST_DOMAIN = 'ils-stock-transaction'


class MockILSStockDataSynchronization(ILSStockDataSynchronization):

    def process_data(self, task, chunk):
        for facility in chunk:
            task(self, facility)


class TestStockTransactionSync(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.stock_api_object = MockILSStockDataSynchronization(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        self.api_object = ILSGatewayAPI(TEST_DOMAIN, self.endpoint)
        self.api_object.prepare_commtrack_config()
        config = ILSGatewayConfig()
        config.domain = TEST_DOMAIN
        config.enabled = True
        config.all_stock_data = True
        config.password = 'dummy'
        config.username = 'dummy'
        config.url = 'http://test-api.com/'
        config.save()
        l1 = Location(
            name='Test location 1',
            external_id='3445',
            location_type='FACILITY',
            domain=TEST_DOMAIN
        )

        l2 = Location(
            name='Test location 2',
            external_id='4407',
            location_type='FACILITY',
            domain=TEST_DOMAIN
        )

        l1.save()
        l2.save()

        SupplyPointCase.create_from_location(TEST_DOMAIN, l1)
        SupplyPointCase.create_from_location(TEST_DOMAIN, l2)

        with open(os.path.join(self.datapath, 'sample_products.json')) as f:
            for product_json in json.loads(f.read()):
                self.api_object.product_sync(Product(product_json))

        StockTransaction.objects.all().delete()

    def test_stock_data_migration(self):
        stock_data_task(self.stock_api_object)
        self.assertEqual(SupplyPointStatus.objects.all().count(), 5)
        self.assertEqual(
            SupplyPointStatus.objects.all().values_list('location_id', flat=True).distinct().count(), 2
        )
        self.assertEqual(StockTransaction.objects.filter(report__domain=TEST_DOMAIN).count(), 16)
        self.assertEqual(DeliveryGroupReport.objects.all().count(), 4)
        self.assertEqual(
            DeliveryGroupReport.objects.all().values_list('location_id', flat=True).distinct().count(), 2
        )
        self.assertEqual(StockState.objects.all().count(), 6)
        self.assertEqual(StockReport.objects.all().count(), 2)

    def test_stock_data_migration2(self):
        StockDataCheckpoint.objects.create(
            domain=TEST_DOMAIN,
            api='',
            limit=1000,
            offset=0,
            date=datetime.datetime(2015, 7, 1)
        )
        stock_data_task(self.stock_api_object)
        self.assertEqual(SupplyPointStatus.objects.all().count(), 5)
        self.assertEqual(
            SupplyPointStatus.objects.all().values_list('location_id', flat=True).distinct().count(), 2
        )
        self.assertEqual(StockTransaction.objects.filter(report__domain=TEST_DOMAIN).count(), 15)
        self.assertEqual(DeliveryGroupReport.objects.all().count(), 4)
        self.assertEqual(
            DeliveryGroupReport.objects.all().values_list('location_id', flat=True).distinct().count(), 2
        )
        self.assertEqual(StockState.objects.all().count(), 6)
        self.assertEqual(StockReport.objects.all().count(), 2)

    def tearDown(self):
        Domain.get_by_name(TEST_DOMAIN).delete()
