import json
import os
from django.test import TestCase
from corehq.apps.commtrack.dbaccessors import \
    get_supply_point_case_by_location_id
from corehq.apps.commtrack.tests.util import (bootstrap_products,
                                              bootstrap_domain as initial_bootstrap)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.products.models import SQLProduct
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.api import Location, EWSApi, Product
from custom.ewsghana.models import FacilityInCharge
from custom.ewsghana.tests import MockEndpoint

TEST_DOMAIN = 'ewsghana-commtrack-locations-test'


class LocationSyncTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        cls.api_object = EWSApi(TEST_DOMAIN, cls.endpoint)
        cls.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        bootstrap_products(TEST_DOMAIN)
        cls.api_object.prepare_commtrack_config()
        with open(os.path.join(cls.datapath, 'sample_products.json')) as f:
            for p in json.loads(f.read()):
                cls.api_object.product_sync(Product(p))

    def setUp(self):
        delete_all_locations()

    def test_create_non_facility_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[0])

        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(ewsghana_location.name, location.name)
        self.assertEqual(ewsghana_location.location_type, location.type)
        self.assertEqual(ewsghana_location.longitude, float(location.longitude))
        self.assertEqual(ewsghana_location.latitude, float(location.latitude))
        self.assertEqual(ewsghana_location.parent, location.parent_id)
        self.assertFalse(ewsghana_location.is_archived)

        sql_location = ewsghana_location.sql_location
        self.assertEqual(ewsghana_location.get_id, sql_location.location_id)
        self.assertIsNotNone(sql_location.id)
        self.assertIsNone(ewsghana_location.linked_supply_point())
        self.assertIsNone(sql_location.supply_point_id)

    def test_create_facility_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[1])

        with open(os.path.join(self.datapath, 'sample_products.json')) as f:
            for p in json.loads(f.read()):
                self.api_object.product_sync(Product(p))
        self.assertEqual(8, SQLProduct.objects.filter(domain=TEST_DOMAIN).count())
        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(ewsghana_location.name, location.supply_points[0].name)
        self.assertEqual(ewsghana_location.site_code, location.supply_points[0].code)
        self.assertEqual("Hospital", ewsghana_location.location_type)
        self.assertEqual(ewsghana_location.longitude, float(location.longitude))
        self.assertEqual(ewsghana_location.latitude, float(location.latitude))
        self.assertFalse(ewsghana_location.is_archived)

        sql_location = ewsghana_location.sql_location
        self.assertEqual(ewsghana_location.get_id, sql_location.location_id)
        self.assertEqual(int(sql_location.parent.external_id), location.parent_id)
        self.assertIsNotNone(sql_location.id)
        self.assertIsNotNone(sql_location.supply_point_id)
        supply_point = get_supply_point_case_by_location_id(
            TEST_DOMAIN, sql_location.location_id)
        self.assertIsNotNone(supply_point)
        self.assertEqual(supply_point.location, ewsghana_location)
        self.assertEqual(location.supply_points[0].id, int(supply_point.external_id))
        self.assertEqual(location.supply_points[0].name, supply_point.name)
        self.assertSetEqual(set(location.supply_points[0].products),
                            {product.code for product in ewsghana_location.sql_location.products})

    def test_create_region_with_two_supply_points(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[4])

        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(2, SQLLocation.objects.filter(
            domain=TEST_DOMAIN,
            location_type__administrative=False).count()
        )
        self.assertIsNone(ewsghana_location.linked_supply_point())
        self.assertIsNone(ewsghana_location.sql_location.supply_point_id)
        self.assertEqual(location.name, ewsghana_location.sql_location.name)
        self.assertEqual(location.code, ewsghana_location.sql_location.site_code)
        self.assertFalse(ewsghana_location.is_archived)

    def test_facility_without_supply_point(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[5])

        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(1, SQLLocation.objects.filter(
            domain=TEST_DOMAIN,
            location_type__administrative=False).count()
        )

        supply_point = ewsghana_location.linked_supply_point()
        self.assertIsNotNone(supply_point)
        self.assertIsNotNone(ewsghana_location.sql_location.supply_point_id)

        self.assertEqual(supply_point.external_id, '')
        self.assertEqual(ewsghana_location.name, location.name)
        self.assertEqual(ewsghana_location.site_code, location.code)
        self.assertTrue(ewsghana_location.is_archived)

    def test_facility_with_inactive_and_active_supply_point(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[6])

        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual("tsactive", ewsghana_location.site_code)
        self.assertEqual("Active Test hospital", ewsghana_location.name)
        self.assertFalse(ewsghana_location.is_archived)

    def test_locations_with_duplicated_site_code(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[8])
        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(SQLLocation.objects.filter(site_code='duplicated', domain=TEST_DOMAIN).count(), 1)
        self.assertEqual(ewsghana_location.site_code, "duplicated")
        self.assertNotEqual(ewsghana_location.parent.site_code, "duplicated")

    def test_edit_location_with_duplicated_code(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            locations = json.loads(f.read())
            location = Location(locations[8])
            district = Location(locations[7])
        self.api_object.location_sync(location)
        ews_district = self.api_object.location_sync(district)
        self.assertNotEqual(ews_district.site_code, "duplicated")

    def test_edit_reporting_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[1])

        self.api_object.location_sync(location)
        location.name = 'edited'
        location.code = 'edited'
        edited = self.api_object.location_sync(location)
        # shouldn't change because we use name and code from supply point not from location
        self.assertEqual(edited.name, 'Central Regional Medical Store')
        self.assertEqual(edited.site_code, 'crms')

        location.supply_points[0].name = 'edited'
        location.supply_points[0].code = 'edited'
        location.supply_points[0].products = ['alk', 'abc', 'ad']
        edited = self.api_object.location_sync(location)
        self.assertEqual(edited.name, 'edited')
        self.assertEqual(edited.site_code, 'edited')
        self.assertEqual(edited.sql_location.products.count(), 3)
        self.assertListEqual(list(edited.sql_location.products.values_list('code', flat=True).order_by('code')),
                             ['abc', 'ad', 'alk'])

    def test_location_with_products(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[1])

        ews_location = self.api_object.location_sync(location)
        self.assertListEqual(
            list(ews_location.sql_location.products.values_list('code', flat=True).order_by('code')),
            ['ad', 'al']
        )

    def test_location_without_products(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[8])

        ews_location = self.api_object.location_sync(location)
        self.assertEqual(ews_location.sql_location.products.count(), 0)

    def test_edit_non_facility_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[0])

        ewsghana_location = self.api_object.location_sync(location)
        self.assertEqual(ewsghana_location.name, "Test country")
        self.assertEqual(ewsghana_location.site_code, "testcountry")

        location.name = "edited"
        location.code = "edited"
        ewsghana_location = self.api_object.location_sync(location)

        self.assertEqual(ewsghana_location.name, "edited")
        self.assertEqual(ewsghana_location.site_code, "edited")

    def test_facility_in_charge(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[1])

        ewsghana_location = self.api_object.location_sync(location)
        in_charges = FacilityInCharge.objects.filter(location=ewsghana_location.sql_location)
        self.assertEqual(in_charges.count(), 1)
        user = CommCareUser.get_by_user_id(in_charges[0].user_id)
        self.assertIsNotNone(user)
