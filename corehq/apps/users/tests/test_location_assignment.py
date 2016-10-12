import copy

from django.test import TestCase

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.management.commands import add_multi_location_property
from corehq.util.test_utils import generate_cases


class CCUserLocationAssignmentTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'my-domain'
        cls.domain_obj = create_domain(cls.domain)

        cls.loc1 = make_loc('1', 'loc1', cls.domain)
        cls.loc2 = make_loc('2', 'loc2', cls.domain)
        cls.loc_ids = [l.location_id for l in [cls.loc1, cls.loc2]]

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        for l in [cls.loc1, cls.loc2]:
            l.delete()

    def setUp(self):
        super(CCUserLocationAssignmentTest, self).setUp()
        self.user = CommCareUser.create(
            domain=self.domain,
            username='cc1',
            password='***',
        )

    def tearDown(self):
        self.user.delete()
        super(CCUserLocationAssignmentTest, self).tearDown()

    def test_set_location(self):
        self.user.set_location(self.loc1)
        self.assertPrimaryLocation(self.loc1.location_id)
        self.assertAssignedLocations([self.loc1.location_id])

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

    def test_deleting_location_updates_user(self):
        self.user.reset_locations(self.loc_ids)
        self.loc1.full_delete()
        self.loc2.full_delete()
        self.assertAssignedLocations([])

    def assertPrimaryLocation(self, expected):
        self.assertEqual(self.user.location_id, expected)
        self.assertEqual(self.user.user_data.get('commcare_location_id'), expected)
        self.assertTrue(expected in self.user.assigned_location_ids)

    def assertAssignedLocations(self, expected_location_ids):
        user = CommCareUser.get(self.user._id)
        self.assertListEqual(user.assigned_location_ids, expected_location_ids)
        actual_ids = user.user_data.get('commcare_location_ids', '')
        actual_ids = actual_ids.split(' ') if actual_ids else []
        self.assertListEqual(actual_ids, expected_location_ids)

    def assertNonPrimaryLocation(self, expected):
        self.assertNotEqual(self.user.location_id, expected)
        self.assertTrue(expected in self.user.assigned_location_ids)
        self.assertTrue(expected in self.user.user_data.get('commcare_location_ids'))


class WebUserLocationAssignmentTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'my-domain'
        cls.domain_obj = create_domain(cls.domain)

        cls.loc1 = make_loc('1', 'loc1', cls.domain)
        cls.loc2 = make_loc('2', 'loc2', cls.domain)
        cls.loc_ids = [l.location_id for l in [cls.loc1, cls.loc2]]

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        for l in [cls.loc1, cls.loc2]:
            l.delete()

    def setUp(self):
        super(WebUserLocationAssignmentTest, self).setUp()
        self.user = WebUser.create(
            domain=self.domain,
            username='web1',
            password='***',
        )

    def tearDown(self):
        self.user.delete()
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


def cc_user(location_id=None, assigned_location_ids=None, user_data={}):
    doc = {
        'location_id': location_id,
    }
    if assigned_location_ids is not None:
        doc['assigned_location_ids'] = assigned_location_ids

    user = copy.deepcopy(doc)
    user.update({
        'doc_type': 'CommCareUser',
        'user_data': user_data,
        'domain_membership': doc
    })
    return user


def user_data(val):
    return {'commcare_location_ids': val}


def web_user(location_id=None, assigned_location_ids=None):
    user = cc_user(location_id, assigned_location_ids)

    return {
        'doc_type': 'WebUser',
        'domain_memberships': [user['domain_membership']]
    }


@generate_cases([
    (
        cc_user(),
        cc_user(),
        False
    ),
    (
        cc_user('ca', ['ca'], user_data=user_data('ca')),
        cc_user('ca', ['ca'], user_data=user_data('ca')),
        False
    ),
    (
        cc_user('ab'),
        cc_user('ab', ['ab'], user_data=user_data('ab')),
        True
    ),
    (
        cc_user('a', ['b']),
        cc_user('a', ['b', 'a'], user_data=user_data('b a')),
        True
    ),
    (
        web_user(),
        web_user(),
        False
    ),
    (
        web_user('a', ['a']),
        web_user('a', ['a']),
        False
    ),
    (
        web_user('a'),
        web_user('a', ['a']),
        True
    ),
    (
        web_user('a', ['b']),
        web_user('a', ['b', 'a']),
        True
    ),
])
def test_migration(self, user, expected, should_migrate):
    migration = add_multi_location_property.Command().migrate_user(user)
    self.assertEqual(bool(migration), should_migrate)
    if should_migrate:
        actual = migration.doc
        self.assertEqual(actual, expected)
