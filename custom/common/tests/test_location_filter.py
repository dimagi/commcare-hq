from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import WebUser
from custom.common.filters import RestrictedLocationDrillDown


class TestLocationFilter(LocationHierarchyTestCase):
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
        super(TestLocationFilter, self).setUp()
        self.web_user = WebUser.create(self.domain, 'test', 'test')

    def tearDown(self):
        delete_all_users()
        super(TestLocationFilter, self).tearDown()

    def test_user_without_location(self):
        self.restrict_user_to_assigned_locations(self.web_user)
        self.assertListEqual(RestrictedLocationDrillDown(self.domain, self.web_user).get_locations_json(), [])

    def test_user_with_single_location(self):
        self.web_user.add_to_assigned_locations(self.domain, self.locations['Boston'])
        self.restrict_user_to_assigned_locations(self.web_user)

        locations = RestrictedLocationDrillDown(self.domain, self.web_user).get_locations_json()
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0]['name'], 'Massachusetts')

    def test_user_with_multiple_locations(self):
        self.web_user.add_to_assigned_locations(self.domain, self.locations['Boston'])
        self.web_user.add_to_assigned_locations(self.domain, self.locations['Somerville'])
        self.restrict_user_to_assigned_locations(self.web_user)

        locations = RestrictedLocationDrillDown(self.domain, self.web_user).get_locations_json()
        self.assertEqual(len(locations), 1)

        self.assertEqual(len(locations[0]['children'][0]['children']), 1)
        self.assertEqual(len(locations[0]['children'][1]['children']), 1)
        self.assertEqual(locations[0]['children'][0]['children'][0]['name'], 'Somerville')
        self.assertEqual(locations[0]['children'][1]['children'][0]['name'], 'Boston')
