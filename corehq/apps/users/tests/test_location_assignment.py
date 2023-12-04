from datetime import datetime

from django.test import TestCase
from corehq.apps.es.tests.utils import es_test

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.client import manager
from corehq.apps.es.users import user_adapter
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.es.testing import sync_users_to_es


@es_test(requires=[user_adapter], setup_class=True)
class CCUserLocationAssignmentTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(CCUserLocationAssignmentTest, cls).setUpClass()
        cls.domain = 'my-domain'
        cls.domain_obj = create_domain(cls.domain)

        cls.loc1 = make_loc('1', 'loc1', cls.domain)
        cls.loc2 = make_loc('2', 'loc2', cls.domain)
        cls.loc_ids = [l.location_id for l in [cls.loc1, cls.loc2]]

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        delete_all_locations()
        super(CCUserLocationAssignmentTest, cls).tearDownClass()

    def setUp(self):
        super(CCUserLocationAssignmentTest, self).setUp()
        self.user = CommCareUser.create(
            domain=self.domain,
            username='cc1',
            password='***',
            created_by=None,
            created_via=None,
            last_login=datetime.now()
        )

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        super(CCUserLocationAssignmentTest, self).tearDown()

    def test_set_location(self):
        self.user.set_location(self.loc1)
        self.assertPrimaryLocation(self.loc1.location_id)
        self.assertAssignedLocations([self.loc1.location_id])

    def test_set_sql_location(self):
        loc = self.loc1.sql_location
        self.user.set_location(loc)
        self.assertPrimaryLocation(loc.location_id)
        self.assertAssignedLocations([loc.location_id])

    def test_location_append(self):
        self.user.add_to_assigned_locations(self.loc1)
        self.assertPrimaryLocation(self.loc1.location_id)  # first location added becomes primary
        self.assertAssignedLocations([self.loc1.location_id])

        self.user.add_to_assigned_locations(self.loc2)
        self.assertNonPrimaryLocation(self.loc2.location_id)  # subsequent additions are not primary
        self.assertAssignedLocations(self.loc_ids)

    def test_reset_locations(self):
        self.user.reset_locations(self.loc_ids)
        self.assertAssignedLocations(self.loc_ids)
        self.assertPrimaryLocation(self.loc1.location_id)  # should fall back to loc1 as primary
        self.assertNonPrimaryLocation(self.loc2.location_id)

    def test_unset_primary_location(self):
        # assigned to only one location
        self.user.set_location(self.loc1)
        self.user.unset_location()
        self.assertEqual(self.user.location_id, None)  # primary location should be cleared
        self.assertAssignedLocations([])

        # assigned to multiple locations
        self.user.reset_locations(self.loc_ids)
        self.user.unset_location(fall_back_to_next=True)
        self.assertPrimaryLocation(self.loc2.location_id)  # should fall back to loc2 as primary
        self.user.unset_location(fall_back_to_next=True)
        self.assertEqual(self.user.location_id, None)  # primary location should be cleared

    def test_unset_by_location_id(self):
        # unset a primary location
        self.user.reset_locations(self.loc_ids)
        self.user.unset_location_by_id(self.loc1.location_id, fall_back_to_next=True)
        self.assertAssignedLocations([self.loc2.location_id])  # loc1 should be removed
        self.assertPrimaryLocation(self.loc2.location_id)  # should fall back to loc2 as primary
        # unset a non primary location
        self.user.reset_locations(self.loc_ids)
        self.user.unset_location_by_id(self.loc2.location_id, fall_back_to_next=True)
        self.assertAssignedLocations([self.loc1.location_id])  # loc2 should be removed
        self.assertPrimaryLocation(self.loc1.location_id)  # loc1 should still be primary location
        self.user.unset_location_by_id(self.loc1.location_id, fall_back_to_next=True)
        self.assertAssignedLocations([])

    @sync_users_to_es()
    def test_deleting_location_updates_user(self):
        self.user.reset_locations(self.loc_ids)
        manager.index_refresh(user_adapter.index_name)
        self.loc1.sql_location.full_delete()
        self.loc2.sql_location.full_delete()
        self.assertAssignedLocations([])

    def test_no_commit(self):
        self.user.set_location(self.loc1, commit=False)
        saved_user = CommCareUser.get(self.user._id)
        self.assertEqual(saved_user.get_sql_location(self.domain), None)

    def test_create_with_location(self):
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)
        self.user = CommCareUser.create(
            domain=self.domain,
            username='cc2',
            password='***',
            created_by=None,
            created_via=None,
            last_login=datetime.now(),
            location=self.loc1,
        )
        self.assertPrimaryLocation(self.loc1.location_id)
        self.assertAssignedLocations([self.loc1.location_id])

    def assertPrimaryLocation(self, expected):
        self.assertEqual(self.user.location_id, expected)
        self.assertEqual(self.user.get_user_data(self.domain).get('commcare_location_id'), expected)
        self.assertTrue(expected in self.user.assigned_location_ids)

    def assertAssignedLocations(self, expected_location_ids):
        user = CommCareUser.get(self.user._id)
        self.assertListEqual(user.assigned_location_ids, expected_location_ids)
        actual_ids = user.get_user_data(self.domain).get('commcare_location_ids', '')
        actual_ids = actual_ids.split(' ') if actual_ids else []
        self.assertListEqual(actual_ids, expected_location_ids)

    def assertNonPrimaryLocation(self, expected):
        self.assertNotEqual(self.user.location_id, expected)
        self.assertTrue(expected in self.user.assigned_location_ids)
        self.assertTrue(expected in self.user.get_user_data(self.domain).get('commcare_location_ids'))


class WebUserLocationAssignmentTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(WebUserLocationAssignmentTest, cls).setUpClass()
        cls.domain = 'my-domain'
        cls.domain_obj = create_domain(cls.domain)

        cls.loc1 = make_loc('1', 'loc1', cls.domain)
        cls.loc2 = make_loc('2', 'loc2', cls.domain)
        cls.loc_ids = [l.location_id for l in [cls.loc1, cls.loc2]]

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        delete_all_locations()
        super(WebUserLocationAssignmentTest, cls).tearDownClass()

    def setUp(self):
        super(WebUserLocationAssignmentTest, self).setUp()
        self.user = WebUser.create(
            domain=self.domain,
            username='web1',
            password='***',
            created_by=None,
            created_via=None,
            last_login=datetime.now()
        )

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        super(WebUserLocationAssignmentTest, self).tearDown()

    def test_set_location(self):
        self.user.set_location(self.domain, self.loc1)
        self.assertPrimaryLocation(self.loc1.location_id)
        self.assertAssignedLocations([self.loc1.location_id])

    def test_reset_locations(self):
        self.user.reset_locations(self.domain, self.loc_ids)
        self.assertAssignedLocations(self.loc_ids)
        self.assertPrimaryLocation(self.loc1.location_id)
        self.assertNonPrimaryLocation(self.loc2.location_id)

    def test_location_append(self):
        self.user.add_to_assigned_locations(self.domain, self.loc1)
        self.assertPrimaryLocation(self.loc1.location_id)  # first location added becomes primary
        self.assertAssignedLocations([self.loc1.location_id])

        self.user.add_to_assigned_locations(self.domain, self.loc2)
        self.assertNonPrimaryLocation(self.loc2.location_id)  # subsequent additions are not primary
        self.assertAssignedLocations(self.loc_ids)

    def test_unset_primary_location(self):
        # assigned to only one location
        self.user.set_location(self.domain, self.loc1)
        self.user.unset_location(self.domain)
        self.assertEqual(self.user.location_id, None)  # primary location should be cleared
        self.assertAssignedLocations([])

        # assigned to multiple locations
        self.user.reset_locations(self.domain, self.loc_ids)
        self.user.unset_location(self.domain, fall_back_to_next=True)
        self.assertPrimaryLocation(self.loc2.location_id)  # should fall back to loc2 as primary
        self.user.unset_location(self.domain, fall_back_to_next=True)
        self.assertEqual(self.user.location_id, None)  # primary location should be cleared

    def test_unset_by_location_id(self):
        # unset a primary location
        self.user.reset_locations(self.domain, self.loc_ids)
        self.user.unset_location_by_id(self.domain, self.loc1.location_id, fall_back_to_next=True)
        self.assertAssignedLocations([self.loc2.location_id])  # loc1 should be removed
        self.assertPrimaryLocation(self.loc2.location_id)  # should fall back to loc2 as primary
        # unset a non primary location
        self.user.reset_locations(self.domain, self.loc_ids)
        self.user.unset_location_by_id(self.domain, self.loc2.location_id, fall_back_to_next=True)
        self.assertAssignedLocations([self.loc1.location_id])  # loc2 should be removed
        self.assertPrimaryLocation(self.loc1.location_id)  # loc1 should still be primary location

    def assertPrimaryLocation(self, expected):
        membership = self.user.get_domain_membership(self.domain)
        self.assertEqual(membership.location_id, expected)
        self.assertTrue(expected in membership.assigned_location_ids)

    def assertAssignedLocations(self, expected_location_ids):
        membership = self.user.get_domain_membership(self.domain)
        self.assertListEqual(membership.assigned_location_ids, expected_location_ids)

    def assertNonPrimaryLocation(self, expected):
        membership = self.user.get_domain_membership(self.domain)
        self.assertNotEqual(membership.location_id, expected)
        self.assertTrue(expected in membership.assigned_location_ids)
