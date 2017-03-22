from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import WebUser
from custom.m4change.reports import get_location_hierarchy_by_id


class TestLocationHierarchy(LocationHierarchyTestCase):
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

    def setUp(self):
        super(TestLocationHierarchy, self).setUp()
        self.web_user = WebUser.create(self.domain, 'test', 'test')

    def tearDown(self):
        delete_all_users()
        super(TestLocationHierarchy, self).tearDown()

    def test_no_location(self):
        self.assertEqual(len(get_location_hierarchy_by_id(None, self.domain, self.web_user)), 8)

    def test_with_location(self):
        self.assertEqual(
            len(get_location_hierarchy_by_id(self.locations['Middlesex'].location_id, self.domain, self.web_user)),
            3
        )

    def test_no_location_restricted(self):
        self.web_user.add_to_assigned_locations(self.domain, self.locations['Middlesex'])
        self.restrict_user_to_assigned_locations(self.web_user)

        self.assertEqual(len(get_location_hierarchy_by_id(None, self.domain, self.web_user)), 3)

    def test_with_location_restricted(self):
        self.web_user.add_to_assigned_locations(self.domain, self.locations['Middlesex'])
        self.restrict_user_to_assigned_locations(self.web_user)

        self.assertEqual(
            len(
                get_location_hierarchy_by_id(
                    self.locations['Massachusetts'].location_id,
                    self.domain,
                    self.web_user
                )
            ), 3
        )
