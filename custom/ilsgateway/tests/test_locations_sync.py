import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import Location
from custom.ilsgateway.api import Location as Loc
from custom.ilsgateway.commtrack import sync_ilsgateway_location

TEST_DOMAIN = 'ilsgateway-commtrack-webusers-test'

class LocationSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        for location in Location.by_domain(TEST_DOMAIN):
            location.delete()

    def test_create_location(self):
        with open(os.path.join(self.datapath, 'sample_location.json')) as f:
            location = Loc.from_json(json.loads(f.read()))

        ilsgateway_location = sync_ilsgateway_location(TEST_DOMAIN, None, location)
        self.assertEqual(ilsgateway_location.name, location.name)
        self.assertEqual(ilsgateway_location.location_type, location.type)
        self.assertEqual(ilsgateway_location.longitude, location.longitude)
        self.assertEqual(ilsgateway_location.latitude, location.latitude)
        self.assertEqual(ilsgateway_location.parent, location.parent)