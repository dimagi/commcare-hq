from ..models import SQLLocation
from .util import LocationHierarchyTestCase


class TestLocationQuerysetMethods(LocationHierarchyTestCase):
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

    def test_filter_by_user_input(self):
        middlesex_locs = (SQLLocation.objects
                          .filter_by_user_input(self.domain, "Middlesex"))
        self.assertItemsEqual(
            ['Middlesex'],
            [loc.name for loc in middlesex_locs]
        )

    def test_filter_path_by_user_input(self):
        middlesex_locs = (SQLLocation.objects
                          .filter_path_by_user_input(self.domain, "Middlesex"))
        self.assertItemsEqual(
            ['Middlesex', 'Cambridge', 'Somerville'],
            [loc.name for loc in middlesex_locs]
        )

    def test_filter_by_partial_match(self):
        middlesex_locs = (SQLLocation.objects
                          .filter_path_by_user_input(self.domain, "Middle"))
        self.assertItemsEqual(
            ['Middlesex', 'Cambridge', 'Somerville'],
            [loc.name for loc in middlesex_locs]
        )
