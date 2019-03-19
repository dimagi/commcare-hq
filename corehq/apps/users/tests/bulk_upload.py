from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy
from django.test import SimpleTestCase, TestCase
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.users.bulkupload import (
    check_duplicate_usernames,
    check_existing_usernames,
    UserUploadError,
    create_or_update_users_and_groups
)
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.models import CommCareUser, UserRole, Permissions
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.domain.models import Domain
from mock import patch


class TestUserBulkUpload(TestCase, DomainSubscriptionMixin):
    def setUp(self):
        super(TestUserBulkUpload, self).setUp()
        delete_all_users()
        self.domain_name = 'mydomain'
        self.domain = Domain(name=self.domain_name)
        self.domain.save()
        self.user_specs = [{
            'username': 'hello',
            'user_id': 'should not update',
            'name': 'Another One', 'language': None,
            'is_active': 'True',
            'phone-number': '23424123',
            'password': 123,
            'email': None
        }]

        permissions = Permissions(edit_apps=True, view_reports=True)
        self.role = UserRole.get_or_create_with_permissions(self.domain.name, permissions, 'edit-apps')

    def tearDown(self):
        self.role.delete()
        self.domain.delete()
        super(TestUserBulkUpload, self).tearDown()

    @property
    def user(self):
        return CommCareUser.get_by_username('{}@{}.commcarehq.org'.format(
            self.user_specs[0]['username'],
            self.domain.name))

    def test_upload_with_user_id(self):
        bulk_upload_async(
            self.domain.name,
            list(self.user_specs),
            list([]),
        )

        self.assertNotEqual(self.user_specs[0]['user_id'], self.user._id)
        self.assertEqual(self.user_specs[0]['phone-number'], self.user.phone_number)
        self.assertEqual(self.user_specs[0]['name'], self.user.name)

    @patch('corehq.apps.users.bulkupload.domain_has_privilege', lambda x, y: True)
    def test_location_not_list(self):
        self.setup_locations()
        updated_user_spec = deepcopy(self.user_specs[0])

        # location_code can also just be string instead of array for single location assignmentss
        updated_user_spec["location_code"] = self.loc1.site_code
        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assertEqual(self.user.location_id, self.user.user_data.get('commcare_location_id'))
        # multiple locations
        self.assertListEqual([self.loc1._id], self.user.assigned_location_ids)

    @patch('corehq.apps.users.bulkupload.domain_has_privilege', lambda x, y: True)
    def test_location_unknown_site_code(self):
        self.setup_locations()
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["location_code"] = ['unknownsite']

        # location_code should be an array of multiple excel columns
        # with self.assertRaises(UserUploadError):
        result = create_or_update_users_and_groups(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )
        self.assertEqual(len(result["rows"]), 1)

    @patch('corehq.apps.users.bulkupload.domain_has_privilege', lambda x, y: True)
    def test_location_add(self):
        self.setup_locations()
        updated_user_spec = deepcopy(self.user_specs[0])

        updated_user_spec["location_code"] = [a.site_code for a in [self.loc1, self.loc2]]
        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )
        # first location should be primary location
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assertEqual(self.user.location_id, self.user.user_data.get('commcare_location_id'))
        # multiple locations
        self.assertListEqual([l._id for l in [self.loc1, self.loc2]], self.user.assigned_location_ids)
        # non-primary location
        self.assertTrue(self.loc2._id in self.user.user_data.get('commcare_location_ids'))

    @patch('corehq.apps.users.bulkupload.domain_has_privilege', lambda x, y: True)
    def test_location_remove(self):
        self.setup_locations()
        updated_user_spec = deepcopy(self.user_specs[0])
        # first assign both locations
        updated_user_spec["location_code"] = [a.site_code for a in [self.loc1, self.loc2]]
        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )

        # deassign all locations
        updated_user_spec["location_code"] = []
        updated_user_spec["user_id"] = self.user._id
        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )

        # user should have no locations
        self.assertEqual(self.user.location_id, None)
        self.assertEqual(self.user.user_data.get('commcare_location_id'), None)
        self.assertListEqual(self.user.assigned_location_ids, [])

    @patch('corehq.apps.users.bulkupload.domain_has_privilege', lambda x, y: True)
    def test_primary_location_replace(self):
        self.setup_locations()
        updated_user_spec = deepcopy(self.user_specs[0])

        # first assign to loc1
        updated_user_spec["location_code"] = [a.site_code for a in [self.loc1, self.loc2]]
        create_or_update_users_and_groups(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )

        # user's primary location should be loc1
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assertEqual(self.user.user_data.get('commcare_location_id'), self.loc1._id)
        self.assertEqual(self.user.user_data.get('commcare_location_ids'), " ".join([self.loc1._id, self.loc2._id]))
        self.assertListEqual(self.user.assigned_location_ids, [self.loc1._id, self.loc2._id])

        # reassign to loc2
        updated_user_spec["location_code"] = [self.loc2.site_code]
        updated_user_spec["user_id"] = self.user._id
        create_or_update_users_and_groups(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )

        # user's location should now be loc2
        self.assertEqual(self.user.location_id, self.loc2._id)
        self.assertEqual(self.user.user_data.get('commcare_location_ids'), self.loc2._id)
        self.assertEqual(self.user.user_data.get('commcare_location_id'), self.loc2._id)
        self.assertListEqual(self.user.assigned_location_ids, [self.loc2._id])

    @patch('corehq.apps.users.bulkupload.domain_has_privilege', lambda x, y: True)
    def test_location_replace(self):
        self.setup_locations()
        updated_user_spec = deepcopy(self.user_specs[0])

        # first assign to loc1
        updated_user_spec["location_code"] = [self.loc1.site_code]
        create_or_update_users_and_groups(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )

        # reassign to loc2
        updated_user_spec["location_code"] = [self.loc2.site_code]
        updated_user_spec["user_id"] = self.user._id
        create_or_update_users_and_groups(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )

        # user's location should now be loc2
        self.assertEqual(self.user.location_id, self.loc2._id)
        self.assertEqual(self.user.user_data.get('commcare_location_id'), self.loc2._id)
        self.assertListEqual(self.user.assigned_location_ids, [self.loc2._id])

    def setup_locations(self):
        self.loc1 = make_loc('loc1', type='state', domain=self.domain_name)
        self.loc2 = make_loc('loc2', type='state', domain=self.domain_name)

    def test_numeric_user_name(self):
        """
        Test that bulk upload doesn't choke if the user's name is a number
        """
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["name"] = 1234

        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )
        self.assertEqual(self.user.full_name, "1234")

    def test_empty_user_name(self):
        """
        This test confirms that a name of None doesn't set the users name to
        "None" or anything like that.
        """
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["name"] = None

        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )
        self.assertEqual(self.user.full_name, "")

    def test_upper_case_email(self):
        """
        Ensure that bulk upload throws a proper error when the email has caps in it
        """
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["email"] = 'IlOvECaPs@gmaiL.Com'

        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )
        self.assertEqual(self.user.email, updated_user_spec['email'].lower())

    def test_set_role(self):
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["role"] = self.role.name

        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, updated_user_spec['role'])


class TestUserBulkUploadStrongPassword(TestCase, DomainSubscriptionMixin):
    def setUp(self):
        super(TestUserBulkUploadStrongPassword, self).setUp()
        delete_all_users()
        self.domain_name = 'mydomain'
        self.domain = Domain(name=self.domain_name)
        self.domain.strong_mobile_passwords = True
        self.domain.save()
        self.user_specs = [{
            'username': 'tswift',
            'user_id': '1989',
            'name': 'Taylor Swift',
            'language': None,
            'is_active': 'True',
            'phone-number': '8675309',
            'password': 'TaylorSwift89!',
            'email': None
        }]

    def tearDown(self):
        self.domain.delete()
        super(TestUserBulkUploadStrongPassword, self).tearDown()

    def test_duplicate_password(self):
        user_spec = [{
            'username': 'thiddleston',
            'user_id': '1990',
            'name': 'Tom Hiddleston',
            'language': None,
            'is_active': 'True',
            'phone-number': '8675309',
            'password': 'TaylorSwift89!',
            'email': None
        }]

        rows = bulk_upload_async(
            self.domain.name,
            list(user_spec + self.user_specs),
            list([]),
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], 'Provide a unique password for each mobile worker')

    def test_weak_password(self):
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["password"] = '123'

        rows = bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], 'Please provide a stronger password')


class TestUserBulkUploadUtils(SimpleTestCase):

    def test_check_duplicate_usernames(self):
        user_specs = [
            {
                'username': 'hello',
                'user_id': 'should not update',
            },
            {
                'username': 'hello',
                'user_id': 'other id',
            },
        ]

        self.assertRaises(UserUploadError, check_duplicate_usernames, user_specs)

    def test_no_duplicate_usernames(self):
        user_specs = [
            {
                'username': 'hello',
                'user_id': 'should not update',
            },
            {
                'username': 'goodbye',
                'user_id': 'other id',
            },
        ]

        try:
            check_duplicate_usernames(user_specs)
        except UserUploadError:
            self.fail('UserUploadError incorrectly raised')

    def test_existing_username_with_no_id(self):
        user_specs = [
            {
                'username': 'hello',
            },
        ]

        with patch('corehq.apps.users.bulkupload.get_existing_usernames',
                return_value=['hello@domain.commcarehq.org']):
            self.assertRaises(UserUploadError, check_existing_usernames, user_specs, 'domain')
