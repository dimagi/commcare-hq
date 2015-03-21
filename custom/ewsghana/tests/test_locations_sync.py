import json
import os
from django.test import TestCase
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import Location as CouchLocation
from corehq.apps.products.models import SQLProduct
from custom.ewsghana.api import Location, EWSApi, Product
from custom.ewsghana.tests import MockEndpoint

TEST_DOMAIN = 'ewsghana-commtrack-locations-test'


class LocationSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = EWSApi(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        for location in CouchLocation.by_domain(TEST_DOMAIN):
            location.delete()

    def test_create_non_facility_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[0])

        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(ewsghana_location.name, location.name)
        self.assertEqual(ewsghana_location.location_type, location.type)
        self.assertEqual(ewsghana_location.longitude, float(location.longitude))
        self.assertEqual(ewsghana_location.latitude, float(location.latitude))
        self.assertEqual(ewsghana_location.parent, location.parent_id)

        sql_location = ewsghana_location.sql_location
        self.assertEqual(ewsghana_location.get_id, sql_location.location_id)
        self.assertIsNotNone(sql_location.id)
        self.assertIsNone(sql_location.supply_point_id)

    def test_create_facility_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[1])

        with open(os.path.join(self.datapath, 'sample_products.json')) as f:
            for p in json.loads(f.read()):
                self.api_object.product_sync(Product(p))
        self.assertEqual(8, SQLProduct.objects.filter(domain=TEST_DOMAIN).count())
        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(ewsghana_location.name, location.name)
        self.assertEqual("Regional Medical Store", ewsghana_location.location_type)
        self.assertEqual(ewsghana_location.longitude, float(location.longitude))
        self.assertEqual(ewsghana_location.latitude, float(location.latitude))

        sql_location = ewsghana_location.sql_location
        self.assertEqual(ewsghana_location.get_id, sql_location.location_id)
        self.assertEqual(int(sql_location.parent.external_id), location.parent_id)
        self.assertIsNotNone(sql_location.id)
        self.assertIsNotNone(sql_location.supply_point_id)
        supply_point = SupplyPointCase.get_by_location_id(TEST_DOMAIN, sql_location.location_id)
        self.assertIsNotNone(supply_point)
        self.assertEqual(location.supply_points[0].id, int(supply_point.external_id))
        self.assertEqual(location.supply_points[0].name, supply_point.name)
        self.assertListEqual(location.supply_points[0].products,
                             [product.code for product in ewsghana_location.sql_location.products])
