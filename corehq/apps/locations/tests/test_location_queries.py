from __future__ import absolute_import
from nose.tools import with_setup
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.util.test_utils import generate_cases

from ..models import SQLLocation
from .util import LocationHierarchyTestCase, setup_locations_and_types


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


class FilterPathTestCase(LocationHierarchyTestCase):
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
        ('England', [
            ('London', [
                ('London', []),
            ]),
            ('Cambridgeshire', [
                ('Cambridge', []),
            ]),
        ]),
    ]


@generate_cases([
    ('Middlesex', ['Massachusetts/Middlesex',
                   'Massachusetts/Middlesex/Cambridge',
                   'Massachusetts/Middlesex/Somerville']),
    ('Cambridge', ['Massachusetts/Middlesex/Cambridge',
                   'England/Cambridgeshire',
                   'England/Cambridgeshire/Cambridge']),
    ('"Cambridge"', ['Massachusetts/Middlesex/Cambridge',
                     'England/Cambridgeshire/Cambridge']),
    ('Engl/Cambridge', ['England/Cambridgeshire',
                        'England/Cambridgeshire/Cambridge']),
    ('Eng/"Cambridge"', ['England/Cambridgeshire/Cambridge']),
    ('"Eng"/Cambridge', []),
], FilterPathTestCase)
def test_filter_path_by_user_input(self, input_string, expected):
    actual = (SQLLocation.objects
              .filter_path_by_user_input(self.domain, input_string))
    self.assertItemsEqual(expected, [loc.get_path_display() for loc in actual])


class TestLocationQuerysetMethods(BaseTestLocationQuerysetMethods):

    def test_filter_by_user_input(self):
        middlesex_locs = (SQLLocation.objects
                          .filter_by_user_input(self.domain, "Middlesex"))
        self.assertItemsEqual(
            ['Middlesex'],
            [loc.name for loc in middlesex_locs]
        )

    def test_filter_by_partial_match(self):
        middlesex_locs = (SQLLocation.objects
                          .filter_path_by_user_input(self.domain, "Middle"))
        self.assertItemsEqual(
            ['Middlesex', 'Cambridge', 'Somerville'],
            [loc.name for loc in middlesex_locs]
        )


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
