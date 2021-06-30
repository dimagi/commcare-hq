from copy import deepcopy
from django.contrib.admin.models import LogEntry

from django.test import TestCase

from mock import patch, mock

from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
)
from corehq.apps.domain.models import Domain
from corehq.apps.user_importer.importer import (
    create_or_update_users_and_groups,
)
from corehq.apps.user_importer.models import UserUploadRecord
from corehq.apps.user_importer.tasks import import_users_and_groups
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import (
    CommCareUser, DomainPermissionsMirror, SQLUserRole, WebUser, Invitation
)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.const import USER_CHANGE_VIA_BULK_IMPORTER
from corehq.extensions.interface import disable_extensions


class TestMobileUserBulkUpload(TestCase, DomainSubscriptionMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()
        cls.domain_name = 'mydomain'
        cls.domain = Domain.get_or_create_with_name(name=cls.domain_name)
        cls.other_domain = Domain.get_or_create_with_name(name='other-domain')
        cls.uploading_user = WebUser.create(cls.domain_name, "admin@xyz.com", 'password', None, None,
                                            is_superuser=True)

        cls.role = SQLUserRole.create(cls.domain.name, 'edit-apps')
        cls.other_role = SQLUserRole.create(cls.domain.name, 'admin')
        cls.patcher = patch('corehq.apps.user_importer.tasks.UserUploadRecord')
        cls.patcher.start()

        cls.definition = CustomDataFieldsDefinition(domain=cls.domain_name,
                                                    field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='key',
                is_required=False,
                label='Key',
                regex='^[A-G]',
                regex_msg='Starts with A-G',
            ),
            Field(
                slug='mode',
                is_required=False,
                label='Mode',
                choices=['major', 'minor']
            ),
        ])
        cls.definition.save()
        cls.profile = CustomDataFieldsProfile(
            name='melancholy',
            fields={'mode': 'minor'},
            definition=cls.definition,
        )
        cls.profile.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.other_domain.delete()
        cls.patcher.stop()
        cls.definition.delete()
        super().tearDownClass()

    def tearDown(self):
        Invitation.objects.all().delete()
        delete_all_users()

    @property
    def user(self):
        return CommCareUser.get_by_username('{}@{}.commcarehq.org'.format(
            'hello',
            self.domain.name))

    def _get_spec(self, delete_keys=None, **kwargs):
        spec = {
            'username': 'hello',
            'name': 'Another One',
            'language': None,
            'is_active': 'True',
            'phone-number': '23424123',
            'password': 123,
            'email': None
        }
        if delete_keys:
            for key in delete_keys:
                spec.pop(key)
        spec.update(kwargs)
        return spec

    def test_upload_with_missing_user_id(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id='missing')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )

        self.assertIsNone(self.user)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_not_list(self):
        self.setup_locations()

        # location_code can also just be string instead of array for single location assignmentss
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=self.loc1.site_code)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assertEqual(self.user.location_id, self.user.metadata.get('commcare_location_id'))
        # multiple locations
        self.assertListEqual([self.loc1._id], self.user.assigned_location_ids)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_unknown_site_code(self):
        self.setup_locations()

        # location_code should be an array of multiple excel columns
        # with self.assertRaises(UserUploadError):
        result = create_or_update_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code='unknownsite')],
            self.uploading_user
        )
        self.assertEqual(len(result["rows"]), 1)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_add(self):
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        # first location should be primary location
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assertEqual(self.user.location_id, self.user.metadata.get('commcare_location_id'))
        # multiple locations
        self.assertListEqual([l._id for l in [self.loc1, self.loc2]], self.user.assigned_location_ids)
        # non-primary location
        self.assertTrue(self.loc2._id in self.user.metadata.get('commcare_location_ids'))

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_remove(self):
        self.setup_locations()
        # first assign both locations
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )

        # deassign all locations
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[], user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )

        # user should have no locations
        self.assertEqual(self.user.location_id, None)
        self.assertEqual(self.user.metadata.get('commcare_location_id'), None)
        self.assertListEqual(self.user.assigned_location_ids, [])

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_primary_location_replace(self):
        self.setup_locations()
        # first assign to loc1
        create_or_update_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            self.uploading_user
        )

        # user's primary location should be loc1
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assertEqual(self.user.metadata.get('commcare_location_id'), self.loc1._id)
        self.assertEqual(self.user.metadata.get('commcare_location_ids'), " ".join([self.loc1._id, self.loc2._id]))
        self.assertListEqual(self.user.assigned_location_ids, [self.loc1._id, self.loc2._id])

        # reassign to loc2
        create_or_update_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[self.loc2.site_code], user_id=self.user._id)],
            self.uploading_user
        )

        # user's location should now be loc2
        self.assertEqual(self.user.location_id, self.loc2._id)
        self.assertEqual(self.user.metadata.get('commcare_location_ids'), self.loc2._id)
        self.assertEqual(self.user.metadata.get('commcare_location_id'), self.loc2._id)
        self.assertListEqual(self.user.assigned_location_ids, [self.loc2._id])

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_replace(self):
        self.setup_locations()

        # first assign to loc1
        create_or_update_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[self.loc1.site_code])],
            self.uploading_user
        )

        # reassign to loc2
        create_or_update_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[self.loc2.site_code], user_id=self.user._id)],
            self.uploading_user
        )

        # user's location should now be loc2
        self.assertEqual(self.user.location_id, self.loc2._id)
        self.assertEqual(self.user.metadata.get('commcare_location_id'), self.loc2._id)
        self.assertListEqual(self.user.assigned_location_ids, [self.loc2._id])

    def setup_locations(self):
        self.loc1 = make_loc('loc1', type='state', domain=self.domain_name)
        self.loc2 = make_loc('loc2', type='state', domain=self.domain_name)

    def test_numeric_user_name(self):
        """
        Test that bulk upload doesn't choke if the user's name is a number
        """
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(name=1234)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.full_name, "1234")

    def test_empty_user_name(self):
        """
        This test confirms that a name of None doesn't set the users name to
        "None" or anything like that.
        """
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(name=None)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.full_name, "")

    def test_metadata(self):
        # Set metadata
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'F#'})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain', 'key': 'F#'})

        # Update metadata
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'Bb'}, user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain', 'key': 'Bb'})

        # Clear metadata
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': ''}, user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain'})

        # Allow falsy but non-blank values
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'play_count': 0}, user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain', 'play_count': 0})

    def test_uncategorized_data(self):
        # Set data
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(uncategorized_data={'tempo': 'presto'})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain', 'tempo': 'presto'})

        # Update data
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(uncategorized_data={'tempo': 'andante'}, user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain', 'tempo': 'andante'})

        # Clear metadata
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(uncategorized_data={'tempo': ''}, user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain'})

    def test_uncategorized_data_clear(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'tempo': 'andante'})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain', 'tempo': 'andante'})

        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'tempo': ''}, user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {'commcare_project': 'mydomain'})

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_metadata_ignore_system_fields(self):
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'F#'}, location_code=self.loc1.site_code)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'mydomain',
            'commcare_location_id': self.loc1.location_id,
            'commcare_location_ids': self.loc1.location_id,
            'commcare_primary_case_sharing_id': self.loc1.location_id,
            'key': 'F#',
        })

        import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id=self.user.user_id, data={'key': 'G#'}, location_code=self.loc1.site_code)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'mydomain',
            'key': 'G#',
            'commcare_location_id': self.loc1.location_id,
            'commcare_location_ids': self.loc1.location_id,
            'commcare_primary_case_sharing_id': self.loc1.location_id,
        })

    def test_metadata_profile(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'F#', PROFILE_SLUG: self.profile.id})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'mydomain',
            'key': 'F#',
            'mode': 'minor',
            PROFILE_SLUG: self.profile.id,
        })

    def test_metadata_profile_redundant(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={PROFILE_SLUG: self.profile.id, 'mode': 'minor'})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'mydomain',
            'mode': 'minor',
            PROFILE_SLUG: self.profile.id,
        })
        # Profile fields shouldn't actually be added to user_data
        self.assertEqual(self.user.user_data, {
            'commcare_project': 'mydomain',
            PROFILE_SLUG: self.profile.id,
        })

    def test_metadata_profile_blank(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={PROFILE_SLUG: self.profile.id, 'mode': ''})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'mydomain',
            'mode': 'minor',
            PROFILE_SLUG: self.profile.id,
        })

    def test_metadata_profile_conflict(self):
        rows = import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={PROFILE_SLUG: self.profile.id, 'mode': 'major'})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], "metadata properties conflict with profile: mode")

    def test_metadata_profile_unknown(self):
        bad_id = self.profile.id + 100
        rows = import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={PROFILE_SLUG: bad_id})],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], "Could not find profile with id {}".format(bad_id))

    def test_upper_case_email(self):
        """
        Ensure that bulk upload throws a proper error when the email has caps in it
        """
        email = 'IlOvECaPs@gmaiL.Com'
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(email=email)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.email, email.lower())

    def test_set_role(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)

    def test_tracking_updates(self):
        self.assertEqual(LogEntry.objects.count(), 0)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        log_entry = LogEntry.objects.order_by('action_time').first()
        self.assertEqual(
            log_entry.change_message,
            f"created_via: {USER_CHANGE_VIA_BULK_IMPORTER}")
        log_entry = LogEntry.objects.order_by('action_time').last()
        self.assertEqual(
            log_entry.change_message,
            f"role: {self.role.name}[{self.role.get_id}], updated_via: {USER_CHANGE_VIA_BULK_IMPORTER}")

    def test_blank_is_active(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(is_active='')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertTrue(self.user.is_active)

    def test_update_user_no_username(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec()],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertIsNotNone(self.user)

        import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id=self.user._id, username='')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )

    def test_update_user_numeric_username(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username=123)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertIsNotNone(
            CommCareUser.get_by_username('{}@{}.commcarehq.org'.format('123', self.domain.name))
        )

    def test_upload_with_unconfirmed_account(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(delete_keys=['is_active'], is_account_confirmed='False')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        user = self.user
        self.assertIsNotNone(user)
        self.assertEqual(False, user.is_active)
        self.assertEqual(False, user.is_account_confirmed)

    @mock.patch('corehq.apps.user_importer.importer.send_account_confirmation_if_necessary')
    def test_upload_with_unconfirmed_account_send_email(self, mock_account_confirm_email):
        import_users_and_groups(
            self.domain.name,
            [
                self._get_spec(
                    username='with_email',
                    delete_keys=['is_active'],
                    is_account_confirmed='False',
                    send_confirmation_email='True',
                ),
                self._get_spec(
                    username='no_email',
                    delete_keys=['is_active'],
                    is_account_confirmed='False',
                    send_confirmation_email='False',
                ),
                self._get_spec(
                    username='email_missing',
                    delete_keys=['is_active'],
                    is_account_confirmed='False',
                ),
            ],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(mock_account_confirm_email.call_count, 1)
        self.assertEqual('with_email', mock_account_confirm_email.call_args[0][0].raw_username)

    @mock.patch('corehq.apps.user_importer.importer.Invitation.send_activation_email')
    def test_upload_invite_web_user(self, mock_send_activation_email):
        import_users_and_groups(
            self.domain.name,
            [
                self._get_spec(
                    web_user='a@a.com',
                    is_account_confirmed='False',
                    send_confirmation_email='True',
                    role=self.role.name
                )
            ],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)

    @mock.patch('corehq.apps.user_importer.importer.Invitation')
    def test_upload_add_web_user(self, mock_invitation_class):
        username = 'a@a.com'
        web_user = WebUser.create(self.other_domain.name, username, 'password', None, None)
        mock_invite = mock_invitation_class.return_value
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(web_user='a@a.com', is_account_confirmed='True', role=self.role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        web_user = WebUser.get_by_username(username)
        self.assertFalse(mock_invite.send_activation_email.called)
        self.assertTrue(web_user.is_member_of(self.domain.name))

    def test_upload_edit_web_user(self):
        username = 'a@a.com'
        web_user = WebUser.create(self.domain.name, username, 'password', None, None)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(web_user='a@a.com', role=self.role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        web_user = WebUser.get_by_username(username)
        self.assertEqual(web_user.get_role(self.domain.name).name, self.role.name)

    def test_remove_web_user(self):
        username = 'a@a.com'
        web_user = WebUser.create(self.domain.name, username, 'password', None, None)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(web_user='a@a.com', remove_web_user='True')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        web_user = WebUser.get_by_username(username)
        self.assertFalse(web_user.is_member_of(self.domain.name))

    def test_multi_domain(self):
        dm = DomainPermissionsMirror(source=self.domain.name, mirror=self.other_domain.name)
        dm.save()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username=123, domain=self.other_domain.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertIsNotNone(
            CommCareUser.get_by_username('{}@{}.commcarehq.org'.format('123', self.other_domain.name))
        )

    @mock.patch('corehq.apps.user_importer.importer.Invitation.send_activation_email')
    def test_update_pending_user_role(self, mock_send_activation_email):
        import_users_and_groups(
            self.domain.name,
            [
                self._get_spec(
                    web_user='a@a.com',
                    is_account_confirmed='False',
                    send_confirmation_email='True',
                    role=self.role.name
                )
            ],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)
        self.assertEqual(Invitation.by_email('a@a.com')[0].role.split(":")[1], self.role.get_id)

        added_user_id = self.user._id
        import_users_and_groups(
            self.domain.name,
            [
                self._get_spec(
                    web_user='a@a.com',
                    user_id=added_user_id,
                    is_account_confirmed='False',
                    send_confirmation_email='True',
                    role=self.other_role.name
                )
            ],
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)  # invite only sent once
        self.assertEqual(len(Invitation.by_email('a@a.com')), 1)  # only one invite associated with user
        self.assertEqual(self.user.get_role(self.domain.name).name, self.other_role.name)
        self.assertEqual(Invitation.by_email('a@a.com')[0].role, self.other_role.get_qualified_id())


class TestUserBulkUploadStrongPassword(TestCase, DomainSubscriptionMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.patcher = patch('corehq.apps.user_importer.tasks.UserUploadRecord')
        cls.patcher.start()
        cls.domain_name = 'mydomain'
        cls.domain = Domain(name=cls.domain_name)
        cls.domain.strong_mobile_passwords = True
        cls.domain.save()
        cls.uploading_user = WebUser.create(cls.domain_name, "admin@xyz.com", 'password', None, None,
                                            is_superuser=True)

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.patcher.stop()
        super().tearDownClass()

    def setUp(self):
        super(TestUserBulkUploadStrongPassword, self).setUp()
        delete_all_users()
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

        rows = import_users_and_groups(
            self.domain.name,
            list(user_spec + self.user_specs),
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], "'password' values must be unique")

    @disable_extensions('corehq.apps.domain.extension_points.validate_password_rules')
    def test_weak_password(self):
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["password"] = '123'

        rows = import_users_and_groups(
            self.domain.name,
            list([updated_user_spec]),
            [],
            self.uploading_user,
            mock.MagicMock(),
            False
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], 'Password is not strong enough. Try making your password more complex.')


class TestUserUploadRecord(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()
        cls.domain_name = 'mydomain'
        cls.domain = Domain.get_or_create_with_name(name=cls.domain_name)
        cls.uploading_user = WebUser.create(cls.domain_name, "admin@xyz.com", 'password', None, None,
                                            is_superuser=True)
        cls.spec = {
            'username': 'hello',
            'name': 'Another One',
            'password': 123,
        }

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        UserUploadRecord.objects.all().delete()
        super().tearDownClass()

    def tearDown(self):
        delete_all_users()

    def test_user_upload_record(self):
        upload_record = UserUploadRecord(
            domain=self.domain,
            user_id='5'
        )
        upload_record.save()

        task_result = import_users_and_groups.si(
            self.domain.name,
            [self.spec],
            [],
            self.uploading_user,
            upload_record.pk,
            False
        ).apply()
        rows = task_result.result

        upload_record.refresh_from_db()
        self.assertEqual(rows['messages'], upload_record.result)


class TestWebUserBulkUpload(TestCase, DomainSubscriptionMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()
        cls.domain_name = 'mydomain'
        cls.domain = Domain.get_or_create_with_name(name=cls.domain_name)
        cls.other_domain = Domain.get_or_create_with_name(name='other-domain')
        cls.role = SQLUserRole.create(cls.domain.name, 'edit-apps')
        cls.other_role = SQLUserRole.create(cls.domain.name, 'admin')
        cls.other_domain_role = SQLUserRole.create(cls.other_domain.name, 'view-apps')
        cls.patcher = patch('corehq.apps.user_importer.tasks.UserUploadRecord')
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.other_domain.delete()
        cls.patcher.stop()
        super().tearDownClass()

    def tearDown(self):
        Invitation.objects.all().delete()
        delete_all_users()

    def setup_users(self):
        self.user1 = WebUser.create(self.domain_name, 'hello@world.com', 'password', None, None,
                                    email='hello@world.com', is_superuser=False, first_name='Sally',
                                    last_name='Sitwell')
        self.uploading_user = WebUser.create(self.domain_name, 'upload@user.com', 'password', None, None,
                                             email='upload@user.com', is_superuser=True)

    @property
    def user(self):
        return WebUser.get_by_username('hello@world.com')

    @property
    def user_invite(self):
        return Invitation.objects.filter(domain=self.domain_name, email='invited@user.com').first()

    def _get_spec(self, delete_keys=None, **kwargs):
        spec = {
            'username': 'hello@world.com',
            'first_name': 'Sally',
            'last_name': 'Sitwell',
            'status': 'Active User',
            'email': 'hello@world.com',
            'role': self.role.name,
        }
        if delete_keys:
            for key in delete_keys:
                spec.pop(key)
        spec.update(kwargs)
        return spec

    def _get_invited_spec(self, delete_keys=None, **kwargs):
        spec = {
            'username': 'invited@user.com',
            'status': 'Invited User',
            'email': 'invited@user.com',
            'role': self.role.name,
        }
        if delete_keys:
            for key in delete_keys:
                spec.pop(key)
        spec.update(kwargs)
        return spec

    def test_upload_with_missing_role(self):
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(role='')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertIsNone(self.user_invite)

    def test_upload_existing_web_user(self):
        self.setup_users()
        WebUser.create(self.other_domain.name, 'existing@user.com', 'abc', None, None, email='existing@user.com')
        self.assertIsNone(Invitation.objects.filter(email='existing@user.com').first())
        import_users_and_groups(
            self.domain.name,
            [{'username': 'existing@user.com',
              'status': 'Active User',
              'email': 'existing@user.com',
              'role': self.role.name}],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertIsNotNone(Invitation.objects.filter(email='existing@user.com').first())

    def test_web_user_user_name_change(self):
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(first_name='', last_name='')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        # should not be changed
        self.assertNotEqual(self.user.first_name, "")
        self.assertNotEqual(self.user.last_name, "")

    def test_upper_case_email(self):
        self.setup_users()
        email = 'hELlo@WoRld.Com'
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(email=email)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(self.user.email, email.lower())

    def test_set_role(self):
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)

    def test_update_role_current_user(self):
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.other_role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.other_role.name)

    def test_update_role_invited_user(self):
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(role=self.role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(self.user_invite.get_role_name(), self.role.name)

        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(role=self.other_role.name)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(self.user_invite.get_role_name(), self.other_role.name)

    def test_remove_user(self):
        self.setup_users()
        username = 'a@a.com'
        WebUser.create(self.domain.name, username, 'password', None, None)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username='a@a.com', remove='True')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        web_user = WebUser.get_by_username(username)
        self.assertFalse(web_user.is_member_of(self.domain.name))
        self.assertIsNone(Invitation.objects.filter(domain=self.domain_name, email=username).first())

    def test_remove_invited_user(self):
        Invitation.objects.all().delete()
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec()],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertIsNotNone(self.user_invite)
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(remove='True')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertIsNone(self.user_invite)

    def test_remove_uploading_user(self):
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username=self.uploading_user.username, remove='True')],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        web_user = WebUser.get_by_username(self.uploading_user.username)
        self.assertTrue(web_user.is_member_of(self.domain.name))

    @mock.patch('corehq.apps.user_importer.importer.Invitation.send_activation_email')
    def test_upload_invite(self, mock_send_activation_email):
        self.setup_users()
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec()],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)

    def test_multi_domain(self):
        self.setup_users()
        dm = DomainPermissionsMirror(source=self.domain.name, mirror=self.other_domain.name)
        dm.save()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username='123@email.com',
                            domain=self.other_domain.name,
                            role=self.other_domain_role.name,
                            email='123@email.com'
                            )],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertIsNotNone(Invitation.objects.filter(email='123@email.com').first())
        self.assertEqual(Invitation.objects.filter(email='123@email.com').first().domain, self.other_domain.name)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_web_user_location_add(self):
        self.setup_users()
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        membership = self.user.get_domain_membership(self.domain_name)
        # test that first location should be primary location
        self.assertEqual(membership.location_id, self.loc1._id)
        # test for multiple locations
        self.assertListEqual([loc._id for loc in [self.loc1, self.loc2]], membership.assigned_location_ids)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_web_user_location_remove(self):
        self.setup_users()
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[], user_id=self.user._id)],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        membership = self.user.get_domain_membership(self.domain_name)
        self.assertEqual(membership.location_id, None)
        self.assertListEqual(membership.assigned_location_ids, [])

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_invite_location_add(self):
        self.setup_users()
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(location_code=[a.site_code for a in [self.loc1]])],
            [],
            self.uploading_user,
            mock.MagicMock(),
            True
        )
        self.assertEqual(self.user_invite.supply_point, self.loc1._id)

    def setup_locations(self):
        self.loc1 = make_loc('loc1', type='state', domain=self.domain_name)
        self.loc2 = make_loc('loc2', type='state', domain=self.domain_name)
