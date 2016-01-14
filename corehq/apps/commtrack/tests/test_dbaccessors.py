from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.dbaccessors import \
    get_supply_point_ids_in_domain_by_location, \
    get_supply_point_case_by_location_id, get_supply_point_case_by_location
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import Location


class SupplyPointDBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'supply-point-dbaccessors'
        cls.locations = [
            Location(domain=cls.domain),
            Location(domain=cls.domain),
            Location(domain=cls.domain),
        ]
        Location.get_db().bulk_save(cls.locations)
        cls.supply_points = [
            CommCareCase(domain=cls.domain, type='supply-point',
                         location_id=cls.locations[0]._id),
            CommCareCase(domain=cls.domain, type='supply-point',
                         location_id=cls.locations[1]._id),
            CommCareCase(domain=cls.domain, type='supply-point',
                         location_id=cls.locations[2]._id),
        ]
        locations_by_id = {location.location_id: location
                           for location in cls.locations}
        cls.location_supply_point_pairs = [
            (locations_by_id[supply_point.location_id], supply_point)
            for supply_point in cls.supply_points
        ]
        CommCareCase.get_db().bulk_save(cls.supply_points)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_get_supply_point_ids_in_domain_by_location(self):
        self.assertEqual(
            get_supply_point_ids_in_domain_by_location(self.domain),
            {location.location_id: supply_point.case_id
             for location, supply_point in self.location_supply_point_pairs}
        )

    def test_get_supply_point_case_by_location_id(self):
        actual = get_supply_point_case_by_location_id(
            self.domain, self.locations[0]._id)
        expected = SupplyPointCase.wrap(self.supply_points[0].to_json())
        self.assertEqual(type(actual), type(expected))
        self.assertEqual(actual.to_json(), expected.to_json())

    def test_get_supply_point_case_by_location(self):
        actual = get_supply_point_case_by_location(self.locations[0])
        expected = SupplyPointCase.wrap(self.supply_points[0].to_json())
        self.assertEqual(type(actual), type(expected))
        self.assertEqual(actual.to_json(), expected.to_json())
