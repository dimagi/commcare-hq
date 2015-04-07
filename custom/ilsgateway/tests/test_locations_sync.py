from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import Location, SQLLocation
from custom.ilsgateway.api import Location as Loc, ILSGatewayAPI
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint
from custom.logistics.commtrack import synchronization
from custom.logistics.models import MigrationCheckpoint

TEST_DOMAIN = 'ilsgateway-commtrack-locations-test'


class LocationSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = ILSGatewayAPI(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        for location in Location.by_domain(TEST_DOMAIN):
            location.delete()

    def test_create_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Loc(**json.loads(f.read())[1])

        ilsgateway_location = self.api_object.location_sync(location)
        self.assertEqual(ilsgateway_location.name, location.name)
        self.assertEqual(ilsgateway_location.location_type, location.type)
        self.assertEqual(ilsgateway_location.longitude, float(location.longitude))
        self.assertEqual(ilsgateway_location.latitude, float(location.latitude))
        self.assertEqual(ilsgateway_location.parent, location.parent_id)

    def test_locations_migration(self):
        checkpoint = MigrationCheckpoint(
            domain=TEST_DOMAIN,
            start_date=datetime.utcnow(),
            date=datetime.utcnow(),
            api='product',
            limit=100,
            offset=0
        )
        synchronization('location_facility',
                        self.endpoint.get_locations,
                        self.api_object.location_sync, checkpoint, None, 100, 0, filters=dict(type='facility'))
        self.assertEqual('location_facility', checkpoint.api)
        self.assertEqual(100, checkpoint.limit)
        self.assertEqual(0, checkpoint.offset)
        self.assertEqual(4, len(list(Location.by_domain(TEST_DOMAIN))))
        self.assertEqual(4, SQLLocation.objects.filter(domain=TEST_DOMAIN).count())
        sql_location = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='DM520053')
        self.assertEqual('FACILITY', sql_location.location_type.name)
        self.assertIsNotNone(sql_location.supply_point_id)

        sql_location2 = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='region-dodoma')
        self.assertEqual('REGION', sql_location2.location_type.name)
        self.assertIsNone(sql_location2.supply_point_id)
