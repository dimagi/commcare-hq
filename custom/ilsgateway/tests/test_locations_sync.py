from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import Location
from custom.ilsgateway.api import Location as Loc
from custom.ilsgateway.commtrack import sync_ilsgateway_location, locations_sync
from custom.ilsgateway.models import LogisticsMigrationCheckpoint
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint

TEST_DOMAIN = 'ilsgateway-commtrack-locations-test'


class LocationSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        for location in Location.by_domain(TEST_DOMAIN):
            location.delete()

    def test_create_location(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Loc(**json.loads(f.read())[1])

        ilsgateway_location = sync_ilsgateway_location(TEST_DOMAIN, None, location)
        self.assertEqual(ilsgateway_location.name, location.name)
        self.assertEqual(ilsgateway_location.location_type, location.type)
        self.assertEqual(ilsgateway_location.longitude, float(location.longitude))
        self.assertEqual(ilsgateway_location.latitude, float(location.latitude))
        self.assertEqual(ilsgateway_location.parent, location.parent_id)

    def test_locations_migration(self):
        checkpoint = LogisticsMigrationCheckpoint(
            domain=TEST_DOMAIN,
            start_date=datetime.now(),
            date=datetime.now(),
            api='product',
            limit=1000,
            offset=0
        )
        locations_sync(TEST_DOMAIN, MockEndpoint('http://test-api.com/', 'dummy', 'dummy'),
                       checkpoint,
                       limit=1000,
                       offset=0,
                       filters=dict(type='facility'))
        self.assertEqual('location_facility', checkpoint.api)
        self.assertEqual(1000, checkpoint.limit)
        self.assertEqual(0, checkpoint.offset)
        self.assertEqual(4, len(list(Location.by_domain(TEST_DOMAIN))))
