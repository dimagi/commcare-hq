from ..models import SQLLocation
from .util import LocationHierarchyTestCase, make_loc
from corehq.apps.users.models import WebUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users


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
        self.assertItemsEqual(self.locations.values(), all_locs)

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


class TestLocationQuerysetOrder(LocationHierarchyTestCase):
    domain = 'test-location-queryset-order'
    location_type_names = ['state', 'county', 'city']
    location_structure = []

    def tearDown(self):
        SQLLocation.objects.filter(domain=self.domain).delete()

    def make_loc(self, name, loc_type, parent=None):
        return make_loc(name, domain=self.domain, type=loc_type, parent=parent)

    def test_backwards_insertion(self):
        mass = self.make_loc("Mass", "state")
        suffolk = self.make_loc("Suffolk", "county", mass)
        dorchester = self.make_loc("Dorchester", "city", suffolk)
        boston = self.make_loc("Boston", "city", suffolk)
        middlesex = self.make_loc("Middlesex", "county", mass)
        somerville = self.make_loc("Somerville", "city", middlesex)
        cambridge = self.make_loc("Cambridge", "city", middlesex)
        arlington = self.make_loc("Arlington", "city", middlesex)

        self.assertEqual(
            list(SQLLocation.objects.filter(domain=self.domain).values_list("name", flat=True)),
            # I know the indentation is weird - it's here to illustrate WHY this is the correct ordering
            [
                "Mass",
                    "Middlesex",
                        "Arlington",
                        "Cambridge",
                        "Somerville",
                    "Suffolk",
                        "Boston",
                        "Dorchester",
            ]
        )

    def test_arbitrary_insertion_with_rearrangement(self):
        cambridge = self.make_loc("Cambridge", "state")

        mass = self.make_loc("Mass", "state")
        suffolk = self.make_loc("Suffolk", "county", mass)
        middlesex = self.make_loc("Middlesex", "county", mass)
        arlington = self.make_loc("Arlington", "city", middlesex)
        boston = self.make_loc("Boston", "city", suffolk)
        dorchester = self.make_loc("Dorchester", "city", suffolk)
        somerville = self.make_loc("Somerville", "city", middlesex)

        cambridge = cambridge.sql_location
        cambridge.parent = middlesex.sql_location
        cambridge.save()

        self.assertEqual(
            list(SQLLocation.objects.filter(domain=self.domain).values_list("name", flat=True)),
            # I know the indentation is weird - it's here to illustrate WHY this is the correct ordering
            [
                "Mass",
                    "Middlesex",
                        "Arlington",
                        "Cambridge",
                        "Somerville",
                    "Suffolk",
                        "Boston",
                        "Dorchester",
            ]
        )
