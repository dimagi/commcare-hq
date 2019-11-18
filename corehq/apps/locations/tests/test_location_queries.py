import pickle

from django.test.utils import override_settings

from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import WebUser

from ..models import SQLLocation
from .util import LocationHierarchyTestCase


class BaseTestLocationQuerysetMethods(LocationHierarchyTestCase):
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
        ]),
        ('California', [
            ('Los Angeles', []),
        ])
    ]


class TestLocationQuerysetMethods(BaseTestLocationQuerysetMethods):

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

    def test_ancestors(self):
        boston_matches = (SQLLocation.objects
                          .filter_by_user_input(self.domain, "Boston"))

        self.assertItemsEqual(
            [loc.name for loc in boston_matches[0].get_ancestors()],
            ['Suffolk', 'Massachusetts']
        )

    def test_ancestor_of_type(self):
        boston = (SQLLocation.objects
                  .filter_by_user_input(self.domain, "Boston"))[0]
        self.assertEqual(
            boston.get_ancestor_of_type('county').name,
            'Suffolk'
        )
        self.assertEqual(
            boston.get_ancestor_of_type('state').name,
            'Massachusetts'
        )

    def test_get_ancestors_with_empty_queryset(self):
        empty = SQLLocation.objects.none()
        locs = SQLLocation.objects.get_queryset_ancestors(empty)
        self.assertEqual(locs.count(), 0)

    def test_get_descendants_with_empty_queryset(self):
        empty = SQLLocation.objects.none()
        locs = SQLLocation.objects.get_queryset_descendants(empty)
        self.assertEqual(locs.count(), 0)

    def test_getitem_with_slice(self):
        locs = SQLLocation.objects.get(name='Suffolk').get_descendants()
        self.assertEqual([x.name for x in locs[:2]], ['Boston'])

    def test_pickle_descendants_query(self):
        locs = SQLLocation.objects.get(name='Suffolk').get_descendants()
        # should not raise excepiton
        pickle.dumps(locs)


class TestLocationScopedQueryset(BaseTestLocationQuerysetMethods):

    @classmethod
    def setUpClass(cls):
        super(TestLocationScopedQueryset, cls).setUpClass()
        delete_all_users()

    def setUp(self):
        super(TestLocationScopedQueryset, self).setUp()
        self.web_user = WebUser.create(self.domain, 'blah', 'password')
        self.web_user.set_location(self.domain, self.locations['Middlesex'])

    def tearDown(self):
        delete_all_users()
        super(TestLocationScopedQueryset, self).tearDown()

    def test_access_all_locations_enabled(self):
        all_locs = (
            SQLLocation.objects.accessible_to_user(self.domain, self.web_user)
        )
        self.assertItemsEqual(list(self.locations.values()), all_locs)

    def test_primary_location_assigned_and_descendants(self):
        self.restrict_user_to_assigned_locations(self.web_user)
        accessible_locs = (
            SQLLocation.objects.accessible_to_user(self.domain, self.web_user)
        )

        self.assertItemsEqual(
            [self.locations[location] for location in ["Middlesex", "Cambridge", "Somerville"]],
            accessible_locs
        )

    def test_location_assigned_and_their_descendants(self):
        self.web_user.add_to_assigned_locations(self.domain, self.locations['California'])
        self.restrict_user_to_assigned_locations(self.web_user)
        accessible_locs = (
            SQLLocation.objects.accessible_to_user(self.domain, self.web_user)
        )

        accessible_loc_names = ["Middlesex", "Cambridge", "Somerville", "California", "Los Angeles"]
        self.assertItemsEqual(
            [self.locations[location] for location in accessible_loc_names],
            accessible_locs
        )

    def test_location_restricted_but_unassigned(self):
        # unassigned users shouldn't be able to access any locations
        unassigned_user = WebUser.create(self.domain, 'unassigned', 'password')
        self.restrict_user_to_assigned_locations(unassigned_user)
        self.assertItemsEqual(
            [],
            SQLLocation.objects.accessible_to_user(self.domain, unassigned_user)
        )

    def test_filter_path_by_user_input(self):
        self.restrict_user_to_assigned_locations(self.web_user)

        # User searching for higher in the hierarchy is only given the items
        # they are allowed to see
        middlesex_locs = (
            SQLLocation.objects
            .filter_path_by_user_input(self.domain, "Massachusetts")
            .accessible_to_user(self.domain, self.web_user)
        )
        self.assertItemsEqual(
            ['Middlesex', 'Cambridge', 'Somerville'],
            [loc.name for loc in middlesex_locs]
        )

        # User searching for a branch they don't have access to get nothing
        no_locs = (
            SQLLocation.objects
            .filter_path_by_user_input(self.domain, "Suffolk")
            .accessible_to_user(self.domain, self.web_user)
        )
        self.assertItemsEqual([], no_locs)
