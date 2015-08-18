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

    def test_filter_by_ancestry(self):
        middlesex_locs = (SQLLocation.objects
                          .filter(domain=self.domain,
                                  name="Middlesex")
                          .include_children())
        self.assertItemsEqual(
            ['Middlesex', 'Cambridge', 'Somerville'],
            [loc.name for loc in middlesex_locs]
        )
