from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import flag_enabled


class OwnerIDTestCase(TestCase):
    domain = 'OwnerIDTestCase'

    @classmethod
    def _mock_user(cls, id):
        class FakeUser(CommCareUser):

            @property
            def project(self):
                return Domain()

        user = FakeUser(_id=id, domain=cls.domain)
        return user

    def test_get_owner_id_no_groups(self):
        user = self._mock_user('test-user-1')
        ids = user.get_owner_ids(self.domain)
        self.assertEqual(1, len(ids))
        self.assertEqual(user._id, ids[0])

    def test_case_sharing_groups_included(self):
        user = self._mock_user('test-user-2')
        group = Group(domain=self.domain, users=['test-user-2'], case_sharing=True)
        group.save()
        ids = user.get_owner_ids(self.domain)
        self.assertEqual(2, len(ids))
        self.assertEqual(user._id, ids[0])
        self.assertEqual(group._id, ids[1])

    def test_non_case_sharing_groups_not_included(self):
        user = self._mock_user('test-user-3')
        group = Group(domain=self.domain, users=['test-user-3'], case_sharing=False)
        group.save()
        ids = user.get_owner_ids(self.domain)
        self.assertEqual(1, len(ids))
        self.assertEqual(user._id, ids[0])


class LocationOwnerIdTests(LocationHierarchyTestCase):
    domain = 'LocationOwnerIdTests'
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
                ('Revere', []),
            ])
        ]),
        ('New York', [
            ('New York City', [
                ('Manhattan', []),
                ('Brooklyn', []),
                ('Queens', []),
            ]),
        ]),
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_types['state'].view_descendants = True
        cls.location_types['state'].save()
        cls.location_types['city'].shares_cases = True
        cls.location_types['city'].save()

    def test_hierarchical_ownership(self):
        user = CommCareUser.create(self.domain, 'username', 'password', None, None)
        user.set_location(self.locations['New York'])
        user.add_to_assigned_locations(self.locations['Suffolk'])
        user.add_to_assigned_locations(self.locations['Somerville'])
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)

        # Only city locations share cases, and only state cases view descendants,
        # so the cities in New York state appear, but not those in Suffolk county
        # Somerville appears to, as it's directly assigned
        self.assertItemsEqual(
            user.get_owner_ids(self.domain),
            [user.user_id] + [self.locations[loc].location_id for loc in
                              ['Manhattan', 'Brooklyn', 'Queens', 'Somerville']]
        )

    def test_web_user(self):
        user = WebUser.create(self.domain, 'username', 'password', None, None)
        user.set_location(self.domain, self.locations['New York'])
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)

        self.assertItemsEqual(
            user.get_owner_ids(self.domain),
            [user.user_id] + [self.locations[loc].location_id for loc in ['Manhattan', 'Brooklyn', 'Queens']]
        )

    @flag_enabled('USH_RESTORE_FILE_LOCATION_CASE_SYNC_RESTRICTION')
    def test_hierarchical_ownership_with_SQL_function(self):
        # Uses the SQL function, but functionality should be exact same as method above
        user = CommCareUser.create(self.domain, 'username', 'password', None, None)
        user.set_location(self.locations['New York'])
        user.add_to_assigned_locations(self.locations['Suffolk'])
        user.add_to_assigned_locations(self.locations['Somerville'])
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)

        self.assertItemsEqual(
            user.get_owner_ids(self.domain),
            [user.user_id] + [self.locations[loc].location_id for loc in
                              ['Manhattan', 'Brooklyn', 'Queens', 'Somerville']]
        )

    @flag_enabled('USH_RESTORE_FILE_LOCATION_CASE_SYNC_RESTRICTION')
    def test_web_user_with_SQL_function(self):
        user = WebUser.create(self.domain, 'username', 'password', None, None)
        user.set_location(self.domain, self.locations['New York'])
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)

        self.assertItemsEqual(
            user.get_owner_ids(self.domain),
            [user.user_id] + [self.locations[loc].location_id for loc in ['Manhattan', 'Brooklyn', 'Queens']]
        )

    @flag_enabled('USH_RESTORE_FILE_LOCATION_CASE_SYNC_RESTRICTION')
    def test_case_sync_restriction_simple(self):
        # Tests `expand_view_child_data_to` setting
        user = WebUser.create(self.domain, 'username', 'password', None, None)
        user.set_location(self.domain, self.locations['New York'])
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)

        self.location_types['state'].expand_view_child_data_to = self.location_types['county']
        self.location_types['state'].shares_cases = True
        self.location_types['state'].save()
        self.location_types['county'].shares_cases = True
        self.location_types['county'].view_descendants = True
        self.location_types['county'].save()
        self.assertItemsEqual(
            user.get_owner_ids(self.domain),
            [user.user_id] + [self.locations[loc].location_id for loc in [
                'New York', 'New York City']]
        )
