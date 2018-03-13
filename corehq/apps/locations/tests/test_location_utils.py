from __future__ import unicode_literals
from ..models import LocationType, SQLLocation
from .util import LocationHierarchyTestCase


class MassachusettsTestCase(LocationHierarchyTestCase):
    location_type_names = ['state', 'county', 'city']
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


class TestLocationsSetup(MassachusettsTestCase):

    def test_location_types(self):
        for lt_name in self.location_type_names:
            in_db = LocationType.objects.get(domain=self.domain, name=lt_name)
            in_dict = self.location_types[lt_name]
            self.assertEqual(lt_name, in_db.name, in_dict.name)

    def test_locations_created(self):
        location_names = ['Massachusetts', 'Middlesex', 'Cambridge',
                          'Somerville', 'Suffolk', 'Boston']
        for name in location_names:
            self.assertIn(name, self.locations)

    def test_parentage(self):
        cambridge = self.locations['Cambridge']
        self.assertEqual(cambridge.parent.name, 'Middlesex')
        self.assertEqual(cambridge.parent.parent.name, 'Massachusetts')


class TestGetLocationsAndChildren(MassachusettsTestCase):

    def test_get_locations_and_children(self):
        names = ['Middlesex', 'Somerville', 'Suffolk']
        result = SQLLocation.objects.get_locations_and_children(
            [self.locations[name].location_id for name in names]
        )
        self.assertItemsEqual(
            [loc.name for loc in result],
            ['Middlesex', 'Cambridge', 'Somerville', 'Suffolk', 'Boston']
        )

    def test_get_locations_and_children2(self):
        names = ['Middlesex', 'Boston']
        result = SQLLocation.objects.get_locations_and_children(
            [self.locations[name].location_id for name in names]
        )
        self.assertItemsEqual(
            [loc.name for loc in result],
            ['Middlesex', 'Cambridge', 'Somerville', 'Boston']
        )
