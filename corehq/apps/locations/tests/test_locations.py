from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.products.models import SQLProduct

from ..models import LocationType, SQLLocation
from .util import LocationHierarchyPerTest, make_loc


class LocationProducts(TestCase):

    def setUp(self):
        self.domain = create_domain('locations-test')
        self.domain.save()

        LocationType.objects.get_or_create(
            domain=self.domain.name,
            name='outlet',
        )

        make_product(self.domain.name, 'apple', 'apple')
        make_product(self.domain.name, 'orange', 'orange')
        make_product(self.domain.name, 'banana', 'banana')
        make_product(self.domain.name, 'pear', 'pear')

        self.loc = make_loc('loc', type='outlet', domain=self.domain.name)

    def tearDown(self):
        # domain delete cascades to everything else
        self.domain.delete()
        LocationType.objects.filter(domain=self.domain.name).delete()

    def test_start_state(self):
        self.assertTrue(self.loc.stocks_all_products)
        self.assertEqual(
            set(SQLProduct.objects.filter(domain=self.domain.name)),
            set(self.loc.products),
        )

    def test_specify_products(self):
        products = [
            SQLProduct.objects.get(name='apple'),
            SQLProduct.objects.get(name='orange'),
        ]
        self.loc.products = products
        self.loc.save()
        self.assertFalse(self.loc.stocks_all_products)
        self.assertEqual(
            set(products),
            set(self.loc.products),
        )

    def test_setting_all_products(self):
        # If all products are set for the location,
        # set stocks_all_products to True
        products = [
            SQLProduct.objects.get(name='apple'),
            SQLProduct.objects.get(name='orange'),
            SQLProduct.objects.get(name='banana'),
            SQLProduct.objects.get(name='pear'),
        ]
        self.loc.products = products
        self.loc.save()
        self.assertTrue(self.loc.stocks_all_products)
        self.assertEqual(
            set(SQLProduct.objects.filter(domain=self.domain.name)),
            set(self.loc.products),
        )


class LocationsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(LocationsTest, cls).setUpClass()
        cls.domain = create_domain('locations-test')
        bootstrap_location_types(cls.domain.name)
        cls.loc = make_loc('loc', type='outlet', domain=cls.domain.name)

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(LocationsTest, cls).tearDownClass()

    def test_location_queries(self):
        test_state1 = make_loc(
            'teststate1',
            type='state',
            parent=self.loc,
            domain=self.domain.name
        )
        test_state2 = make_loc(
            'teststate2',
            type='state',
            parent=self.loc,
            domain=self.domain.name
        )
        test_village1 = make_loc(
            'testvillage1',
            type='village',
            parent=test_state1,
            domain=self.domain.name
        )
        test_village1.site_code = 'tv1'
        test_village1.save()
        test_village2 = make_loc(
            'testvillage2',
            type='village',
            parent=test_state2,
            domain=self.domain.name
        )

        def compare(list1, list2):
            self.assertEqual(
                set(l.location_id for l in list1),
                set(l.location_id for l in list2)
            )

        # descendants
        compare(
            [test_state1, test_state2, test_village1, test_village2],
            self.loc.get_descendants()
        )

        # children
        compare(
            [test_state1, test_state2],
            self.loc.get_children()
        )

        # parent and parent_location_id
        self.assertEqual(
            self.loc.location_id,
            test_state1.parent_location_id
        )
        self.assertEqual(
            self.loc.location_id,
            test_state1.parent.location_id
        )

        compare(
            [self.loc],
            SQLLocation.objects.filter(domain=self.domain.name, parent=None)
        )

        create_domain('rejected')
        bootstrap_location_types('rejected')
        test_village2.domain = 'rejected'
        test_village2.save()
        self.assertEqual(
            {loc.location_id for loc in [self.loc, test_state1, test_state2, test_village1]},
            set(SQLLocation.objects.filter(domain=self.domain.name).location_ids()),
        )


class TestDeleteLocations(LocationHierarchyPerTest):
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

    def test_trickle_down_delete(self):
        self.locations['Middlesex'].delete()
        self.assertItemsEqual(
            SQLLocation.objects.filter(domain=self.domain).values_list('name', flat=True),
            ['Massachusetts', 'Suffolk', 'Boston']
        )

    def test_delete_queryset(self):
        (SQLLocation.objects
         .filter(domain=self.domain,
                 name__in=['Boston', 'Suffolk', 'Cambridge'])
         .delete())
        self.assertItemsEqual(
            SQLLocation.objects.filter(domain=self.domain).values_list('name', flat=True),
            ['Massachusetts', 'Middlesex', 'Somerville']
        )

    def test_delete_queryset_across_domains(self):
        other_domain = 'upside-down-domain'
        create_domain(other_domain)
        location_type = LocationType.objects.create(
            domain=other_domain,
            name="The Upside Down",
            administrative=True,
        )
        self.addCleanup(lambda: location_type.delete())
        SQLLocation.objects.create(
            domain=other_domain, name='Evil Suffolk', location_type=location_type
        )
        self.assertItemsEqual(
            SQLLocation.objects.all().values_list('name', flat=True),
            ['Massachusetts', 'Middlesex', 'Cambridge', 'Somerville', 'Suffolk', 'Boston', 'Evil Suffolk']
        )
        (SQLLocation.objects
         .filter(name__in=['Boston', 'Suffolk', 'Cambridge', 'Evil Suffolk'])
         .delete())
        self.assertItemsEqual(
            SQLLocation.objects.all().values_list('name', flat=True),
            ['Massachusetts', 'Middlesex', 'Somerville']
        )
