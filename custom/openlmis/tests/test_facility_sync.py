import os
from django.test import TestCase
from casexml.apps.case.tests import delete_all_cases
from corehq.apps.commtrack.tests import bootstrap_domain
from corehq.apps.locations.models import Location
from custom.openlmis.api import get_facilities
from custom.openlmis.commtrack import sync_facility_to_supply_point


TEST_DOMAIN = 'openlmis-commtrack-facility-test'

class FacilitySyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        bootstrap_domain(TEST_DOMAIN)
        delete_all_cases()
        for loc in Location.by_domain(TEST_DOMAIN):
            loc.delete()

    def testCreateSupplyPointFromFacility(self):
        with open(os.path.join(self.datapath, 'recent_facilities.rss')) as f:
            recent = list(get_facilities(f.read()))

        [f1, f2] = recent
        self.assertEqual(0, len(list(Location.by_domain(TEST_DOMAIN))))
        sp1 = sync_facility_to_supply_point(TEST_DOMAIN, f1)
        locs = list(Location.by_domain(TEST_DOMAIN))
        self.assertEqual(1, len(locs))
        [loc1] = locs
        # check loc
        self.assertEqual(f1.name, loc1.name)
        self.assertEqual(f1.code, loc1.external_id)

        # check supply point
        self.assertEqual(f1.name, sp1.name)
        self.assertEqual(f1.code, sp1.external_id)
        self.assertEqual(sp1.location._id, loc1._id)
