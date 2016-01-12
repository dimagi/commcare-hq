from ..models import SQLLocation
from .util import LocationHierarchyTestCase


class TestLocationQuerysetMethods(LocationHierarchyTestCase):
    dependent_apps = [
        'corehq.couchapps',
        'corehq.apps.commtrack',
        'corehq.apps.domain',
        'corehq.apps.products',
        'corehq.apps.tzmigration',
        'corehq.apps.users',
        'custom.logistics',
        'custom.ilsgateway',
        'custom.ewsghana',

    ]

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

    def test_get_queryset_descendants(self):
        mass = SQLLocation.objects.get(name='Massachusetts')
        counties = mass.get_children()
        self.assertItemsEqual(
            ['Cambridge', 'Somerville', 'Boston'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(counties)]
        )
        self.assertItemsEqual(
            ['Middlesex', 'Suffolk', 'Cambridge', 'Somerville', 'Boston'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(counties, include_self=True)]
        )
        self.assertItemsEqual(
            ['Middlesex', 'Suffolk', 'Cambridge', 'Somerville', 'Boston'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(
                SQLLocation.objects.filter(name='Massachusetts')
            )],
        )
        self.assertItemsEqual(
            ['Massachusetts', 'Middlesex', 'Suffolk', 'Cambridge', 'Somerville', 'Boston'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(
                SQLLocation.objects.filter(name='Massachusetts'),
                include_self=True
            )],
        )
        self.assertItemsEqual(
            ['Boston'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(
                SQLLocation.objects.filter(name__in=['Suffolk', 'Cambridge'])
            )]
        )
        self.assertItemsEqual(
            ['Boston', 'Suffolk', 'Cambridge'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(
                SQLLocation.objects.filter(name__in=['Suffolk', 'Cambridge']),
                include_self=True,
            )]
        )
        self.assertItemsEqual(
            ['Boston'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(
                SQLLocation.objects.filter(name__in=['Suffolk', 'Boston']),
            )]
        )
        self.assertItemsEqual(
            ['Boston', 'Suffolk'],
            [loc.name for loc in SQLLocation.get_queryset_descendants(
                SQLLocation.objects.filter(name__in=['Suffolk', 'Boston']),
                include_self=True
            )]
        )
