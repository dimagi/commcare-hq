from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.locations.fixtures import LocationSet


class LocationSetTest(SimpleTestCase):

    def test_duplicate_locations(self):
        parent = LocationType(
            domain="test-domain",
            name="parent",
            code="parent",
        )

        child = LocationType(
            domain="test-domain",
            name="child",
            code="child",
            parent_type=parent
        )

        location1 = SQLLocation(
            id="58302461",
            location_id="1",
            name="Some Parent Location",
            location_type=parent
        )
        location2 = SQLLocation(
            id="39825",
            location_id="2",
            name="Some Child Location",
            location_type=child,
            parent=location1
        )
        set_locations = LocationSet([location1, location2])
        self.assertEqual(len(set_locations.by_parent['1']), 1)
        self.assertEqual(len(set_locations.by_parent['2']), 0)

        self.assertEqual(len(set_locations.by_id), 2)

        set_locations.add_location(location1)
        set_locations.add_location(location2)

        self.assertEqual(len(set_locations.by_id), 2)
        self.assertEqual(len(set_locations.by_parent['1']), 1)
        self.assertEqual(len(set_locations.by_parent['2']), 0)
