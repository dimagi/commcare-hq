from django.test import TestCase

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser


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

    def test_reset_locations(self):

        self.user.reset_locations(self.loc_ids)
        self.assertAssignedLocations(self.loc_ids)
        for loc_id in self.loc_ids:
            self.assertNonPrimaryLocation(loc_id)

    def test_unset_by_location_id(self):
        # unset a primary location
        self.user.set_location(self.loc1)
        self.user.reset_locations(self.loc_ids)
        self.assertAssignedLocations(self.loc_ids)
        self.user.unset_location_by_id(self.loc1.location_id)
        self.assertAssignedLocations([self.loc2.location_id])
        # unset a non primary location
        self.user.reset_locations(self.loc_ids)
        self.user.unset_location_by_id(self.loc1.location_id)
        self.assertAssignedLocations([self.loc2.location_id])

    def assertPrimaryLocation(self, expected):
        self.assertEqual(self.user.location_id, expected)
        self.assertEqual(self.user.user_data.get('commcare_location_id'), expected)
        self.assertTrue(expected in self.user.assigned_location_ids)

    def assertAssignedLocations(self, expected_location_ids):
        self.assertListEqual(self.user.assigned_location_ids, expected_location_ids)
        actual_ids = self.user.user_data.get('commcare_location_ids', '')
        actual_ids = actual_ids.split(',')
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
        for loc_id in self.loc_ids:
            self.assertNonPrimaryLocation(loc_id)

    def test_unset_by_location_id(self):
        # unset a primary location
        self.user.set_location(self.domain, self.loc1)
        self.user.reset_locations(self.domain, self.loc_ids)
        self.assertAssignedLocations(self.loc_ids)
        self.user.unset_location_by_id(self.domain, self.loc1.location_id)
        self.assertAssignedLocations([self.loc2.location_id])
        # unset a non primary location
        self.user.reset_locations(self.domain, self.loc_ids)
        self.user.unset_location_by_id(self.domain, self.loc1.location_id)
        self.assertAssignedLocations([self.loc2.location_id])

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
