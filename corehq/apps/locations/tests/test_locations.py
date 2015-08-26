from mock import patch
from corehq.apps.groups.tests import WrapGroupTestMixin
from corehq.apps.locations.models import Location, LocationType, SQLLocation, \
    LOCATION_REPORTING_PREFIX
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.locations.fixtures import location_fixture_generator
from corehq.apps.commtrack.helpers import make_supply_point, make_product
from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.users.models import CommCareUser
from django.test import TestCase, SimpleTestCase
from corehq import toggles
from corehq.apps.groups.exceptions import CantSaveException
from corehq.apps.products.models import SQLProduct
from corehq.apps.domain.shortcuts import create_domain


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


class LocationTestBase(TestCase):
    def setUp(self):
        self.domain = create_domain('locations-test')
        self.domain.convert_to_commtrack()
        bootstrap_location_types(self.domain.name)

        self.loc = make_loc('loc', type='outlet', domain=self.domain.name)
        self.sp = make_supply_point(self.domain.name, self.loc)

        self.user = CommCareUser.create(
            self.domain.name,
            'username',
            'password',
            first_name='Bob',
            last_name='Builder',
        )
        self.user.set_location(self.loc)

    def tearDown(self):
        self.user.delete()
        # domain delete cascades to everything else
        self.domain.delete()


class LocationsTest(LocationTestBase):
    def test_storage_types(self):
        # make sure we can go between sql/couch locs
        sql_loc = SQLLocation.objects.get(name=self.loc.name)
        self.assertEqual(
            sql_loc.couch_location._id,
            self.loc._id
        )

        self.assertEqual(
            sql_loc.id,
            self.loc.sql_location.id
        )

    def test_location_queries(self):
        test_state1 = make_loc(
            'teststate1',
            type='state',
            parent=self.user.location,
            domain=self.domain.name
        )
        test_state2 = make_loc(
            'teststate2',
            type='state',
            parent=self.user.location,
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
                set([l._id for l in list1]),
                set([l._id for l in list2])
            )

        # descendants
        compare(
            [test_state1, test_state2, test_village1, test_village2],
            self.user.location.descendants
        )

        # children
        compare(
            [test_state1, test_state2],
            self.user.location.children
        )

        # siblings
        compare(
            [test_state2],
            test_state1.siblings()
        )

        # parent and parent_id
        self.assertEqual(
            self.user.location._id,
            test_state1.parent_id
        )
        self.assertEqual(
            self.user.location._id,
            test_state1.parent._id
        )


        # is_root
        self.assertTrue(self.user.location.is_root)
        self.assertFalse(test_state1.is_root)

        # Location.root_locations
        compare(
            [self.user.location],
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

        # Location.get_in_domain
        test_village2.domain = 'rejected'
        bootstrap_location_types('rejected')
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

        self.assertEqual(
            {loc._id for loc in [self.user.location, test_state1, test_state2,
                                 test_village1]},
            set(SQLLocation.objects.filter(domain=self.domain.name).location_ids()),
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
            [self.user.location, test_state1, test_state2, test_village1],
            Location.by_domain(self.domain.name)
        )


class LocationGroupTest(LocationTestBase):
    def setUp(self):
        super(LocationGroupTest, self).setUp()

        self.test_state = make_loc(
            'teststate',
            type='state',
            domain=self.domain.name
        )
        self.test_village = make_loc(
            'testvillage',
            type='village',
            parent=self.test_state,
            domain=self.domain.name
        )
        self.test_outlet = make_loc(
            'testoutlet',
            type='outlet',
            parent=self.test_village,
            domain=self.domain.name
        )

        toggles.MULTIPLE_LOCATIONS_PER_USER.set("domain:{}".format(self.domain.name), True)

    def test_group_name(self):
        # just location name for top level
        self.assertEqual(
            'teststate-Cases',
            self.test_state.sql_location.case_sharing_group_object().name
        )

        # locations combined by forward slashes otherwise
        self.assertEqual(
            'teststate/testvillage/testoutlet-Cases',
            self.test_outlet.sql_location.case_sharing_group_object().name
        )

        # reporting group is similar but has no ending
        self.assertEqual(
            'teststate/testvillage/testoutlet',
            self.test_outlet.sql_location.reporting_group_object().name
        )

    def test_id_assignment(self):
        # each should have the same id, but with a different prefix
        self.assertEqual(
            self.test_outlet._id,
            self.test_outlet.sql_location.case_sharing_group_object()._id
        )
        self.assertEqual(
            LOCATION_REPORTING_PREFIX + self.test_outlet._id,
            self.test_outlet.sql_location.reporting_group_object()._id
        )

    def test_group_properties(self):
        # case sharing groups should ... be case sharing
        self.assertTrue(
            self.test_outlet.sql_location.case_sharing_group_object().case_sharing
        )
        self.assertFalse(
            self.test_outlet.sql_location.case_sharing_group_object().reporting
        )

        # and reporting groups reporting
        self.assertFalse(
            self.test_outlet.sql_location.reporting_group_object().case_sharing
        )
        self.assertTrue(
            self.test_outlet.sql_location.reporting_group_object().reporting
        )

        # both should set domain properly
        self.assertEqual(
            self.domain.name,
            self.test_outlet.sql_location.reporting_group_object().domain
        )
        self.assertEqual(
            self.domain.name,
            self.test_outlet.sql_location.case_sharing_group_object().domain
        )

    def test_accessory_methods(self):
        # we need to expose group id without building the group sometimes
        # so lets make sure those match up
        expected_id = self.loc.sql_location.case_sharing_group_object()._id
        self.assertEqual(
            expected_id,
            self.loc.group_id
        )

    def test_not_real_groups(self):
        # accessing a group object should not cause it to save
        # in the DB
        group_obj = self.test_outlet.sql_location.case_sharing_group_object()
        self.assertNotEqual(group_obj.doc_type, 'Group')

    def test_cant_save_wont_save(self):
        group_obj = self.test_outlet.sql_location.case_sharing_group_object()
        with self.assertRaises(CantSaveException):
            group_obj.save()

    def test_custom_data(self):
        # need to put the location data on the
        # group with a special prefix
        self.loc.metadata = {
            'foo': 'bar',
            'fruit': 'banana'
        }
        self.loc.save()

        self.assertDictEqual(
            {
                'commcare_location_type': self.loc.location_type,
                'commcare_location_name': self.loc.name,
                'commcare_location_foo': 'bar',
                'commcare_location_fruit': 'banana'
            },
            self.loc.sql_location.case_sharing_group_object().metadata
        )
        self.assertDictEqual(
            {
                'commcare_location_type': self.loc.location_type,
                'commcare_location_name': self.loc.name,
                'commcare_location_foo': 'bar',
                'commcare_location_fruit': 'banana'
            },
            self.loc.sql_location.reporting_group_object().metadata
        )

    @patch('corehq.apps.domain.models.Domain.uses_locations', lambda: True)
    def test_location_fixture_generator(self):
        """
        This tests the location XML fixture generator. It specifically ensures that no duplicate XML
        nodes are generated when all locations have a parent and multiple locations are enabled.
        """
        self.domain.commtrack_enabled = True
        self.domain.save()
        self.loc.delete()

        state = make_loc(
            'teststate1',
            type='state',
            domain=self.domain.name
        )
        district = make_loc(
            'testdistrict1',
            type='district',
            domain=self.domain.name,
            parent=state
        )
        block = make_loc(
            'testblock1',
            type='block',
            domain=self.domain.name,
            parent=district
        )
        village = make_loc(
            'testvillage1',
            type='village',
            domain=self.domain.name,
            parent=block
        )
        outlet1 = make_loc(
            'testoutlet1',
            type='outlet',
            domain=self.domain.name,
            parent=village
        )
        outlet2 = make_loc(
            'testoutlet2',
            type='outlet',
            domain=self.domain.name,
            parent=village
        )
        outlet3 = make_loc(
            'testoutlet3',
            type='outlet',
            domain=self.domain.name,
            parent=village
        )
        self.user.set_location(outlet2)
        self.user.add_location_delegate(outlet1)
        self.user.add_location_delegate(outlet2)
        self.user.add_location_delegate(outlet3)
        self.user.add_location_delegate(state)
        self.user.save()
        fixture = location_fixture_generator(self.user, '2.0')
        self.assertEquals(len(fixture[0].findall('.//state')), 1)
        self.assertEquals(len(fixture[0].findall('.//outlet')), 3)


class WrapLocationTest(WrapGroupTestMixin, SimpleTestCase):
    document_class = Location
