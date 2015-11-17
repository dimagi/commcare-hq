import os
from django.test import TestCase
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.locations.models import Location, LocationType
from custom.openlmis.api import get_facilities
from custom.openlmis.commtrack import sync_facility_to_supply_point, get_supply_point


TEST_DOMAIN = 'openlmis-commtrack-facility-test'

class FacilitySyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        bootstrap_domain(TEST_DOMAIN)
        delete_all_cases()
        for loc in Location.by_domain(TEST_DOMAIN):
            loc.delete()
        LocationType.objects.get_or_create(
            domain=TEST_DOMAIN,
            name="Lvl3 Hospital",
        )

    def _get_facilities(self):
        with open(os.path.join(self.datapath, 'recent_facilities.rss')) as f:
            return list(get_facilities(f.read()))

    def testCreateSupplyPointFromFacility(self):
        [f1, f2] = self._get_facilities()
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
        self.assertEqual(sp1.location.location_id, loc1._id)

    def testGetSupplyPoint(self):
        [f1, f2] = self._get_facilities()
        self.assertTrue(get_supply_point(TEST_DOMAIN, f1) is None)
        sp1 = sync_facility_to_supply_point(TEST_DOMAIN, f1)
        spback = get_supply_point(TEST_DOMAIN, f1)
        self.assertTrue(spback is not None)
        self.assertEqual(sp1.case_id, spback.case_id)

        # test by code
        spback = get_supply_point(TEST_DOMAIN, f1.code)
        self.assertEqual(sp1.case_id, spback.case_id)
