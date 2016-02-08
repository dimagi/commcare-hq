from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import Location, SQLLocation
from custom.ilsgateway.api import Location as Loc, ILSGatewayAPI
from custom.ilsgateway.models import PendingReportingDataRecalculation
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint
from custom.logistics.api import ApiSyncObject
from custom.logistics.commtrack import synchronization
from custom.logistics.models import MigrationCheckpoint

TEST_DOMAIN = 'ilsgateway-commtrack-locations-test'


class LocationSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = ILSGatewayAPI(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        domain = initial_bootstrap(TEST_DOMAIN)
        CommtrackConfig(domain=domain.name).save()
        self.api_object.prepare_commtrack_config()
        for location in Location.by_domain(TEST_DOMAIN):
            location.delete()

    def test_create_facility_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Loc(**json.loads(f.read())[0])

        ilsgateway_location = self.api_object.location_sync(location)
        self.assertEqual(ilsgateway_location.name, location.name)
        self.assertEqual(ilsgateway_location.location_type, location.type)
        self.assertEqual(ilsgateway_location.longitude, float(location.longitude))
        self.assertEqual(ilsgateway_location.latitude, float(location.latitude))
        self.assertEqual(int(ilsgateway_location.parent.sql_location.external_id), location.parent_id)
        self.assertIsNotNone(ilsgateway_location.linked_supply_point())
        self.assertIsNotNone(ilsgateway_location.sql_location.supply_point_id)

    def test_create_non_facility_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Loc(**json.loads(f.read())[1])

        ilsgateway_location = self.api_object.location_sync(location)
        self.assertEqual(ilsgateway_location.name, location.name)
        self.assertEqual(ilsgateway_location.location_type, location.type)
        self.assertEqual(ilsgateway_location.longitude, float(location.longitude))
        self.assertEqual(ilsgateway_location.latitude, float(location.latitude))
        self.assertIsNone(ilsgateway_location.parent)
        self.assertIsNone(ilsgateway_location.linked_supply_point())
        self.assertIsNone(ilsgateway_location.sql_location.supply_point_id)

    def test_parent_change(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Loc(**json.loads(f.read())[0])

        self.api_object.location_sync(location)
        location.parent_id = 2626
        ilsgateway_location = self.api_object.location_sync(location)
        self.assertEqual(ilsgateway_location.parent.external_id, '2626')

    def test_locations_migration(self):
        checkpoint = MigrationCheckpoint(
            domain=TEST_DOMAIN,
            start_date=datetime.utcnow(),
            date=datetime.utcnow(),
            api='product',
            limit=100,
            offset=0
        )
        location_api = ApiSyncObject(
            'location_facility',
            self.endpoint.get_locations,
            self.api_object.location_sync,
            filters=dict(type='facility')
        )
        synchronization(location_api, checkpoint, None, 100, 0)
        self.assertEqual('location_facility', checkpoint.api)
        self.assertEqual(100, checkpoint.limit)
        self.assertEqual(0, checkpoint.offset)
        self.assertEqual(6, len(list(Location.by_domain(TEST_DOMAIN))))
        self.assertEqual(6, SQLLocation.objects.filter(domain=TEST_DOMAIN).count())
        sql_location = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='DM520053')
        self.assertEqual('FACILITY', sql_location.location_type.name)
        self.assertIsNotNone(sql_location.supply_point_id)

        sql_location2 = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='region-dodoma')
        self.assertEqual('REGION', sql_location2.location_type.name)
        self.assertIsNone(sql_location2.supply_point_id)

    def test_create_excluded_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            locations = [Loc(loc) for loc in json.loads(f.read())[4:]]
        ilsgateway_location = self.api_object.location_sync(locations[0])
        self.assertIsNone(ilsgateway_location)

        self.assertEqual(
            SQLLocation.objects.filter(domain=TEST_DOMAIN, site_code=locations[0].code).count(), 0
        )

        ilsgateway_location = self.api_object.location_sync(locations[1])
        self.assertIsNone(ilsgateway_location)

        self.assertEqual(
            SQLLocation.objects.filter(domain=TEST_DOMAIN, site_code=locations[1].code).count(), 0
        )

        ilsgateway_location = self.api_object.location_sync(locations[2])
        self.assertIsNone(ilsgateway_location)

        self.assertEqual(
            SQLLocation.objects.filter(domain=TEST_DOMAIN, site_code=locations[2].code).count(), 0
        )
