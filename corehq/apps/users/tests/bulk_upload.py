from copy import deepcopy
from django.test import SimpleTestCase, TestCase
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.users.bulkupload import (
    check_duplicate_usernames,
    check_existing_usernames,
    SiteCodeToSupplyPointCache,
    UserLocMapping,
    UserUploadError,
)
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.models import CommCareUser, UserRole, Permissions
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.domain.models import Domain
from corehq.toggles import MULTIPLE_LOCATIONS_PER_USER, NAMESPACE_DOMAIN
from mock import patch


class UserLocMapTest(CommTrackTest):

    def setUp(self):
        super(UserLocMapTest, self).setUp()

        self.user = CommCareUser.create(
            self.domain.name,
            'commcareuser',
            'password',
            phone_numbers=['123123'],
            user_data={},
            first_name='test',
            last_name='user'
        )

        MULTIPLE_LOCATIONS_PER_USER.set(self.user.domain, True, NAMESPACE_DOMAIN)

        self.loc = make_loc('secondloc')
        self.sp = self.loc.linked_supply_point()
        self.cache = SiteCodeToSupplyPointCache(self.domain.name)
        self.mapping = UserLocMapping(self.user.username, self.user.domain, self.cache)

    def test_adding_a_location(self):
        self.mapping.to_add.add(self.loc.site_code)

        self.assertEqual(len(self.user.locations), 0)
        self.mapping.save()
        self.assertEqual(len(self.user.locations), 1)

    def test_removing_a_location(self):
        # first make sure there is one to remove
        self.user.add_location_delegate(self.loc)
        self.assertEqual(len(self.user.locations), 1)

        self.mapping.to_remove.add(self.loc.site_code)
        ret = self.mapping.save()
        self.assertEqual(len(self.user.locations), 0)

    def test_should_not_add_what_is_already_there(self):
        self.mapping.to_add.add(self.loc.site_code)

        self.user.add_location_delegate(self.loc)

        with patch('corehq.apps.hqcase.utils.submit_case_blocks') as submit_blocks:
            self.mapping.save()
            assert not submit_blocks.called, 'Should not submit case block if user already has location'

    def test_should_not_delete_what_is_not_there(self):
        self.mapping.to_remove.add(self.loc.site_code)

        with patch('corehq.apps.hqcase.utils.submit_case_blocks') as submit_blocks:
            self.mapping.save()
            assert not submit_blocks.called, 'Should not submit case block if user already has location'

    def test_location_lookup_caching(self):
        user2 = CommCareUser.create(
            self.domain.name,
            'commcareuser2',
            'password',
            phone_numbers=['123123'],
            user_data={},
            first_name='test',
            last_name='user'
        )
        mapping2 = UserLocMapping(user2.username, user2.domain, self.cache)

        self.mapping.to_add.add(self.loc.site_code)
        mapping2.to_add.add(self.loc.site_code)

        with patch('corehq.form_processor.interfaces.supply.SupplyInterface.get_by_location') as get_supply_point:
            self.mapping.save()
            mapping2.save()
            self.assertEqual(get_supply_point.call_count, 1)


class TestUserBulkUpload(TestCase, DomainSubscriptionMixin):
    def setUp(self):
        super(TestUserBulkUpload, self).setUp()
        delete_all_users()
        self.domain_name = 'mydomain'
        self.domain = Domain(name=self.domain_name)
        self.domain.save()
        self.user_specs = [{
            u'username': u'hello',
            u'user_id': u'should not update',
            u'name': u'Another One', u'language': None,
            u'is_active': u'True',
            u'phone-number': u'23424123',
            u'password': 123,
            u'email': None
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
            list([])
        )

        self.assertNotEqual(self.user_specs[0]['user_id'], self.user._id)
        self.assertEqual(self.user_specs[0]['phone-number'], self.user.phone_number)
        self.assertEqual(self.user_specs[0]['name'], self.user.name)

    @patch('corehq.apps.users.bulkupload.domain_has_privilege', lambda x, y: True)
    def test_location_update(self):
        self.setup_location()
        from copy import deepcopy
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["location_code"] = self.state_code

        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
            list([])
        )
        self.assertEqual(self.user.location_id, self.location._id)
        self.assertEqual(self.user.location_id, self.user.user_data.get('commcare_location_id'))

    def setup_location(self):
        self.state_code = 'my_state'
        self.location = make_loc(self.state_code, type='state', domain=self.domain_name)

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
            list([])
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
            list([])
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
            list([])
        )
        self.assertEqual(self.user.email, updated_user_spec['email'].lower())

    def test_set_role(self):
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["role"] = self.role.name

        bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
            list([])
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
            u'username': u'tswift',
            u'user_id': u'1989',
            u'name': u'Taylor Swift',
            u'language': None,
            u'is_active': u'True',
            u'phone-number': u'8675309',
            u'password': 'TaylorSwift89!',
            u'email': None
        }]

    def tearDown(self):
        self.domain.delete()
        super(TestUserBulkUploadStrongPassword, self).tearDown()

    def test_duplicate_password(self):
        user_spec = [{
            u'username': u'thiddleston',
            u'user_id': u'1990',
            u'name': u'Tom Hiddleston',
            u'language': None,
            u'is_active': u'True',
            u'phone-number': u'8675309',
            u'password': 'TaylorSwift89!',
            u'email': None
        }]

        rows = bulk_upload_async(
            self.domain.name,
            list(user_spec + self.user_specs),
            list([]),
            list([])
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], 'Provide a unique password for each mobile worker')

    def test_weak_password(self):
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["password"] = '123'

        rows = bulk_upload_async(
            self.domain.name,
            list([updated_user_spec]),
            list([]),
            list([])
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], 'Please provide a stronger password')


class TestUserBulkUploadUtils(SimpleTestCase):

    def test_check_duplicate_usernames(self):
        user_specs = [
            {
                u'username': u'hello',
                u'user_id': u'should not update',
            },
            {
                u'username': u'hello',
                u'user_id': u'other id',
            },
        ]

        self.assertRaises(UserUploadError, check_duplicate_usernames, user_specs)

    def test_no_duplicate_usernames(self):
        user_specs = [
            {
                u'username': u'hello',
                u'user_id': u'should not update',
            },
            {
                u'username': u'goodbye',
                u'user_id': u'other id',
            },
        ]

        try:
            check_duplicate_usernames(user_specs)
        except UserUploadError:
            self.fail('UserUploadError incorrectly raised')

    def test_existing_username_with_no_id(self):
        user_specs = [
            {
                u'username': u'hello',
            },
        ]

        with patch('corehq.apps.users.bulkupload.get_user_docs_by_username',
                return_value=[{'username': 'hello@domain.commcarehq.org'}]):
            self.assertRaises(UserUploadError, check_existing_usernames, user_specs, 'domain')
