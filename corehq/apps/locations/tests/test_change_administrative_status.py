"""
When a location type is set from stock-tracking to not stock-tracking, find all
locations of that type and:
close the supply point case,
nullify the supply_point_id,
nullify the StockState sql_location field

When a location type is set from not stock tracking to stock tracking, find all
locations of that type and:
see if there is a closed supply point case with that location id
if so:
  reopen that case
  set the supply_point_id to that
  set the sql_location field on any stock states belonging to that supply point case
otherwise:
  open a new supply point case as normal

Actually, it looks like the view "commtrack/supply_point_by_loc" will do just
fine for this purpose, so we can just use that instead.
"""
from django.test import TestCase
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.commtrack.tests.util import bootstrap_domain
from .util import setup_locations_and_types


class TestChangeStatus(TestCase):
    domain = 'test-change-administrative'
    location_type_names = ['state', 'county', 'city']
    stock_tracking_types = ['city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ])
    ]

    def setUp(self):
        self.domain_obj = bootstrap_domain(self.domain)

        self.location_types, self.locations = setup_locations_and_types(
            self.domain,
            self.location_type_names,
            self.stock_tracking_types,
            self.location_structure,
        )

        self.suffolk = self.locations['Suffolk']
        self.boston = self.locations['Boston']
        self.county_type = self.location_types['county']
        self.city_type = self.location_types['city']

    def tearDown(self):
        self.domain_obj.delete()

    def assertHasSupplyPoint(self, location):
        msg = "'{}' does not have a supply point.".format(location.name)
        self.assertIsNotNone(location.supply_point_id, msg)
        self.assertIsNotNone(location.linked_supply_point(), msg)

    def assertHasNoSupplyPoint(self, location):
        msg = "'{}' should not have a supply point".format(location.name)
        self.assertIsNone(location.supply_point_id, msg)

    def test_change_to_track_stock(self):
        self.assertHasSupplyPoint(self.boston)
        self.assertHasNoSupplyPoint(self.suffolk)

        self.county_type.administrative = False
        self.county_type.save()

        self.assertHasSupplyPoint(self.suffolk)

    def test_change_to_administrative_and_back(self):
        # at first it should have a supply point
        self.assertHasSupplyPoint(self.boston)
        supply_point_id = self.boston.supply_point_id

        self.city_type.administrative = True
        self.city_type.save()

        # Now that it's administrative, it shouldn't have one
        # The case should still exist, but be closed
        self.assertHasNoSupplyPoint(self.boston)
        self.assertTrue(SupplyPointCase.get(supply_point_id).closed)

        self.city_type.administrative = False
        self.city_type.save()

        # The same supply point case should be reopened
        self.assertHasSupplyPoint(self.boston)
        self.assertEqual(self.boston.supply_point_id, supply_point_id)
        self.assertFalse(SupplyPointCase.get(supply_point_id).closed)
