from corehq.apps.locations.models import Location, LocationType
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.commtrack.helpers import make_supply_point, make_product
from corehq.apps.users.models import CommCareUser
from django.test import TestCase
from corehq.apps.products.models import SQLProduct

from corehq.apps.domain.shortcuts import create_domain


class LocationProducts(TestCase):
    def setUp(self):
        self.domain = create_domain('locations-test')
        self.domain.locations_enabled = True
        self.domain.save()

        LocationType.objects.get_or_create(
            domain=self.domain.name,
            name='outlet',
        )

        make_product(self.domain.name, 'apple', 'apple')
        make_product(self.domain.name, 'orange', 'orange')
        make_product(self.domain.name, 'banana', 'banana')
        make_product(self.domain.name, 'pear', 'pear')

        couch_loc = make_loc('loc', type='outlet', domain=self.domain.name)
        self.loc = couch_loc.sql_location

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
    def setUp(self):
        self.domain = create_domain('locations-test')
        self.loc = make_loc('loc')
        self.sp = make_supply_point(self.domain.name, self.loc)

        self.user = CommCareUser.create(
            self.domain.name,
            'username',
            'password',
            first_name='Bob',
            last_name='Builder'
        )
        self.user.save()

        self.user.add_location(self.loc)

    def test_location_queries(self):
        test_state1 = make_loc(
            'teststate1',
            type='state',
            parent=self.user.locations[0]
        )
        test_state2 = make_loc(
            'teststate2',
            type='state',
            parent=self.user.locations[0]
        )
        test_village1 = make_loc(
            'testvillage1',
            type='village',
            parent=test_state1
        )
        test_village1.site_code = 'tv1'
        test_village1.save()
        test_village2 = make_loc(
            'testvillage2',
            type='village',
            parent=test_state2
        )

        def compare(list1, list2):
            self.assertEqual(
                set([l._id for l in list1]),
                set([l._id for l in list2])
            )

        # descendants
        compare(
            [test_state1, test_state2, test_village1, test_village2],
            self.user.locations[0].descendants
        )

        # children
        compare(
            [test_state1, test_state2],
            self.user.locations[0].children
        )

        # siblings
        compare(
            [test_state2],
            test_state1.siblings()
        )

        # parent and parent_id
        self.assertEqual(
            self.user.locations[0]._id,
            test_state1.parent_id
        )
        self.assertEqual(
            self.user.locations[0]._id,
            test_state1.parent._id
        )


        # is_root
        self.assertTrue(self.user.locations[0].is_root)
        self.assertFalse(test_state1.is_root)

        # Location.root_locations
        compare(
            [self.user.locations[0]],
            Location.root_locations(self.domain.name)
        )

        # Location.filter_by_type
        compare(
            [test_village1, test_village2],
            Location.filter_by_type(self.domain.name, 'village')
        )
        compare(
            [test_village1],
            Location.filter_by_type(self.domain.name, 'village', test_state1)
        )

        # Location.filter_by_type_count
        self.assertEqual(
            2,
            Location.filter_by_type_count(self.domain.name, 'village')
        )
        self.assertEqual(
            1,
            Location.filter_by_type_count(self.domain.name, 'village', test_state1)
        )

        # Location.get_in_domain
        test_village2.domain = 'rejected'
        test_village2.save()
        self.assertEqual(
            Location.get_in_domain(self.domain.name, test_village1._id)._id,
            test_village1._id
        )
        self.assertIsNone(
            Location.get_in_domain(self.domain.name, test_village2._id),
        )
        self.assertIsNone(
            Location.get_in_domain(self.domain.name, 'not-a-real-id'),
        )

        # Location.all_locations
        compare(
            [self.user.locations[0], test_state1, test_state2, test_village1],
            Location.all_locations(self.domain.name)
        )

        # Location.by_site_code
        self.assertEqual(
            test_village1._id,
            Location.by_site_code(self.domain.name, 'tv1')._id
        )
        self.assertIsNone(
            None,
            Location.by_site_code(self.domain.name, 'notreal')
        )

        # Location.by_domain
        compare(
            [self.user.locations[0], test_state1, test_state2, test_village1],
            Location.by_domain(self.domain.name)
        )
