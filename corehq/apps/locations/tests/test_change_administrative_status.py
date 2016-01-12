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
from .util import LocationHierarchyTestCase


class TestChangeToTrackStock(LocationHierarchyTestCase):
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

    @classmethod
    def setUpClass(cls):
        super(TestChangeToTrackStock, cls).setUpClass()

    def assertHasSupplyPoint(self, location_name):
        loc = self.locations[location_name]
        msg = "'{}' does not have a supply point.".format(location_name)
        self.assertIsNotNone(loc.supply_point_id, msg)
        self.assertIsNotNone(loc.linked_supply_point(), msg)

    def assertHasNoSupplyPoint(self, location_name):
        loc = self.locations[location_name]
        msg = "'{}' should not have a supply point".format(location_name)
        self.assertIsNone(loc.supply_point_id, msg)

    def test_change_to_track_stock(self):
        self.assertHasSupplyPoint("Cambridge")
        self.assertHasNoSupplyPoint("Middlesex")

        self.location_types["county"].administrative = False
        self.location_types["county"].save()

        # This fails
        self.assertHasSupplyPoint("Middlesex")
