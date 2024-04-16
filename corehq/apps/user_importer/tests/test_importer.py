import datetime
from copy import deepcopy

from django.contrib.admin.models import LogEntry
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils.translation import gettext as _
from django.test.utils import tag

from unittest.mock import patch

from corehq import toggles
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.enterprise.models import EnterpriseMobileWorkerSettings
from corehq.apps.enterprise.tests.utils import (
    create_enterprise_permissions,
    get_enterprise_software_plan,
    get_enterprise_account,
    add_domains_to_enterprise_account,
)
from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import TableauUser, TableauServer
from corehq.apps.reports.const import HQ_TABLEAU_GROUP_NAME
from corehq.apps.reports.tests.test_tableau_api_session import _setup_test_tableau_server
from corehq.apps.reports.tests.test_tableau_api_util import _mock_create_session_responses
from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.helpers import UserChangeLogger
from corehq.apps.user_importer.importer import (
    create_or_update_commcare_users_and_groups,
)
from corehq.apps.user_importer.models import UserUploadRecord
from corehq.apps.user_importer.tasks import import_users_and_groups
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import (
    CommCareUser,
    Invitation,
    UserRole,
    UserHistory,
    WebUser,
    DeactivateMobileWorkerTrigger,
    DeactivateMobileWorkerTriggerUpdateMessage,
    HqPermissions,
)
from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.tests.util import patch_user_data_db_layer
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.const import USER_CHANGE_VIA_BULK_IMPORTER
from corehq.extensions.interface import disable_extensions
from corehq.util.test_utils import flag_enabled

from dimagi.utils.dates import add_months_to_date


class TestUserDataMixin:

    @classmethod
    def setup_userdata(cls):

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
    def tear_down_user_data(cls):
        cls.definition.delete()

    def setup_locations(self):
        self.loc1 = make_loc('loc1', type='state', domain=self.domain_name)
        self.loc2 = make_loc('loc2', type='state', domain=self.domain_name)

    def assert_user_data_equals(self, expected):
        self.assertEqual(self.user.get_user_data(self.domain.name).to_dict(), expected)

    def assert_user_data_contains(self, expected):
        data = self.user.get_user_data(self.domain.name).to_dict()
        actual = {}
        for key in expected.keys():
            if key not in data:
                continue
            actual[key] = data.get(key)

        self.assertDictEqual(actual, expected)

    def assert_user_data_excludes(self, excluded_keys):
        data = self.user.get_user_data(self.domain.name).to_dict()
        found = {}
        for key in excluded_keys:
            if key in data:
                found[key] = data['key']

        self.assertEqual({}, found)

    def _test_user_data(self, is_web_upload=False):
        # Set user_data
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'F#'})],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_equals({
            'commcare_project': 'mydomain', 'key': 'F#', 'commcare_profile': '', 'mode': ''})

        # Update user_data
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'Bb'}, user_id=self.user._id)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_equals({
            'commcare_project': 'mydomain', 'key': 'Bb', 'commcare_profile': '', 'mode': ''})

        # set user data to blank
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': ''}, user_id=self.user._id)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'key': ''})

        # Allow falsy but non-blank values
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 0}, user_id=self.user._id)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'key': 0})

    def _test_user_data_profile(self, is_web_upload=False):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'F#'}, user_profile=self.profile.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )

        self.assert_user_data_equals({
            'commcare_project': 'mydomain',
            'key': 'F#',
            'mode': 'minor',
            PROFILE_SLUG: self.profile.id,
        })
        user_history = UserHistory.objects.get(
            user_id=self.user.get_id,
            changed_by=self.uploading_user.get_id,
            # web users are setup first and then updated
            action=UserModelAction.UPDATE.value if is_web_upload else UserModelAction.CREATE.value
        )
        change_messages = UserChangeMessage.profile_info(self.profile.id, self.profile.name)
        self.assertDictEqual(user_history.change_messages['profile'], change_messages['profile'])

    def _test_user_data_profile_redundant(self, is_web_upload=False):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'mode': 'minor'}, user_profile=self.profile.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'mode': 'minor'})
        # Profile fields shouldn't actually be added to user_data
        self.assertEqual(self.user.get_user_data(self.domain.name).raw, {})

    def _test_user_data_profile_blank(self, is_web_upload=False):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'mode': ''}, user_profile=self.profile.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'mode': 'minor'})

    def _test_required_field_optional_if_profile_set(self, is_web_upload=False):
        required_field = [f for f in self.definition.get_fields() if f.slug == 'mode'][0]
        required_field.is_required = True
        required_field.save()
        import_users_and_groups(
            self.domain.name,
            # mode is marked as is_required but provided via profile
            [self._get_spec(user_profile=self.profile.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'mode': 'minor'})
        # cleanup
        required_field.is_required = False
        required_field.save()

    def _test_user_data_profile_conflict(self, is_web_upload=False):
        rows = import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'mode': 'major'}, user_profile=self.profile.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], "'mode' cannot be set directly")

    def _test_profile_cant_overwrite_existing_data(self, is_web_upload=False):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'mode': 'major'})],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        # This fails because it would silently overwrite the existing "mode"
        rows = import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id=self.user.get_id, user_profile=self.profile.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], "Profile conflicts with existing data")

        # This succeeds because it explicitly blanks out "mode"
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id=self.user.get_id, user_profile=self.profile.name, data={'mode': ''})],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'mode': 'minor'})

    def _test_user_data_profile_unknown(self, is_web_upload=False):
        rows = import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_profile="not_a_real_profile")],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], "Profile 'not_a_real_profile' does not exist")

    def _test_uncategorized_data(self, is_web_upload=False):
        # Set data
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(uncategorized_data={'tempo': 'presto'})],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'tempo': 'presto'})

        # Update data
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(uncategorized_data={'tempo': 'andante'}, user_id=self.user._id)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            is_web_upload
        )
        self.assert_user_data_contains({'tempo': 'andante'})


class TestMobileUserBulkUpload(TestCase, DomainSubscriptionMixin, TestUserDataMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()
        cls.domain_name = 'mydomain'
        cls.domain = Domain.get_or_create_with_name(name=cls.domain_name)
        cls.other_domain = Domain.get_or_create_with_name(name='other-domain')
        create_enterprise_permissions("a@a.com", cls.domain_name, [cls.other_domain.name])

        cls.role_with_upload_permission = UserRole.create(
            cls.domain, 'edit-web-users', permissions=HqPermissions(edit_web_users=True)
        )
        cls.uploading_user = WebUser.create(cls.domain_name, "admin@xyz.com", 'password', None, None,
                                            role_id=cls.role_with_upload_permission.get_id)

        cls.emw_domain = Domain.get_or_create_with_name(name='emw-domain')
        cls.uploading_user.add_as_web_user(cls.emw_domain.name, 'admin')
        one_year_ago = add_months_to_date(datetime.datetime.utcnow(), -12)
        enterprise_plan = get_enterprise_software_plan()
        cls.enterprise_account = get_enterprise_account()
        add_domains_to_enterprise_account(
            cls.enterprise_account,
            [cls.emw_domain],
            enterprise_plan,
            one_year_ago
        )
        toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.set(
            cls.emw_domain.name, True, namespace=toggles.NAMESPACE_DOMAIN
        )
        cls.emw_settings = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.enterprise_account,
            allow_custom_deactivation=True,
        )

        cls.role = UserRole.create(cls.domain.name, 'edit-apps')
        cls.other_role = UserRole.create(cls.domain.name, 'admin')
        cls.upload_record = UserUploadRecord(
            domain=cls.domain_name,
            user_id=cls.uploading_user.get_id
        )
        cls.upload_record.save()
        cls.patcher = patch('corehq.apps.user_importer.tasks.UserUploadRecord')
        cls.patcher.start()
        cls.setup_userdata()

    def setUp(self):
        if WebUser.get_by_user_id(self.uploading_user.get_id) is None:
            self.uploading_user = WebUser.create(self.domain_name, "admin@xyz.com", 'password', None, None,
                                                role_id=self.role_with_upload_permission.get_id)

    @classmethod
    def tearDownClass(cls):
        EnterpriseMobileWorkerSettings.objects.all().delete()
        cls.upload_record.delete()
        cls.domain.delete()
        cls.other_domain.delete()
        cls.emw_domain.delete()
        cls.patcher.stop()
        cls.tear_down_user_data()
        super().tearDownClass()

    def tearDown(self):
        Invitation.objects.all().delete()
        delete_all_users()
        for group in Group.by_domain(self.domain.name):
            group.delete()

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
            'phone-number': ['23424123'],
            'password': 123,
            'email': None,
            'user_profile': None,
        }
        if delete_keys:
            for key in delete_keys:
                spec.pop(key)
        spec.update(kwargs)
        return spec

    def assert_user_data_item(self, key, expected):
        self.assertEqual(self.user.get_user_data(self.domain.name).get(key), expected)

    def test_upload_with_missing_user_id(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id='missing')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assert_user_data_item('commcare_location_id', self.user.location_id)
        # multiple locations
        self.assertListEqual([self.loc1._id], self.user.assigned_location_ids)

        user_history = UserHistory.objects.get(action=UserModelAction.CREATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc1]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        self.assertEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['assigned_location_ids'],
                         [self.loc1.get_id])
        self.assertEqual(user_history.changes['location_id'], self.loc1.get_id)
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_unknown_site_code(self):
        self.setup_locations()

        # location_code should be an array of multiple excel columns
        # with self.assertRaises(UserUploadError):
        result = create_or_update_commcare_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code='unknownsite')],
            self.uploading_user,
            self.upload_record.pk,
        )
        self.assertEqual(len(result["rows"]), 1)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_add(self):
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        # first location should be primary location
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assert_user_data_item('commcare_location_id', self.user.location_id)
        self.assert_user_data_item('commcare_primary_case_sharing_id', self.user.location_id)
        # multiple locations
        self.assertListEqual([loc._id for loc in [self.loc1, self.loc2]], self.user.assigned_location_ids)
        # non-primary location
        self.assert_user_data_item('commcare_location_ids', " ".join([self.loc1._id, self.loc2._id]))

        user_history = UserHistory.objects.get(action=UserModelAction.CREATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc1, self.loc2]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['assigned_location_ids'],
                         [self.loc1.get_id, self.loc2.get_id])
        self.assertEqual(user_history.changes['location_id'], self.loc1.get_id)
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_remove(self):
        self.setup_locations()
        # first assign both locations
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )

        user_history = UserHistory.objects.get(action=UserModelAction.CREATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc1, self.loc2]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['location_id'], self.loc1.get_id)
        self.assertEqual(user_history.changes['assigned_location_ids'],
                         [self.loc1.get_id, self.loc2.get_id])
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

        # deassign all locations
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[], user_id=self.user._id, delete_keys=['password'])],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )

        # user should have no locations
        self.assertEqual(self.user.location_id, None)
        self.assert_user_data_item('commcare_location_id', None)
        self.assertListEqual(self.user.assigned_location_ids, [])

        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([]))
        change_messages.update(UserChangeMessage.primary_location_removed())
        self.assertEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['assigned_location_ids'], [])
        self.assertEqual(user_history.changes['location_id'], None)
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_primary_location_replace(self):
        self.setup_locations()
        # first assign to loc1
        create_or_update_commcare_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            self.uploading_user,
            self.upload_record.pk,
        )

        # user's primary location should be loc1
        self.assertEqual(self.user.location_id, self.loc1._id)
        self.assert_user_data_item('commcare_location_id', self.loc1._id)
        self.assert_user_data_item('commcare_location_ids', " ".join([self.loc1._id, self.loc2._id]))
        self.assertListEqual(self.user.assigned_location_ids, [self.loc1._id, self.loc2._id])

        user_history = UserHistory.objects.get(action=UserModelAction.CREATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc1, self.loc2]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['location_id'], self.loc1._id)
        self.assertEqual(user_history.changes['assigned_location_ids'],
                         [self.loc1.get_id, self.loc2.get_id])
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

        # reassign to loc2
        create_or_update_commcare_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[self.loc2.site_code], user_id=self.user._id)],
            self.uploading_user,
            self.upload_record.pk,
        )

        # user's location should now be loc2
        self.assertEqual(self.user.location_id, self.loc2._id)
        self.assert_user_data_item('commcare_location_ids', self.loc2._id)
        self.assert_user_data_item('commcare_location_id', self.loc2._id)
        self.assertListEqual(self.user.assigned_location_ids, [self.loc2._id])

        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc2]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc2))
        change_messages.update(UserChangeMessage.password_reset())
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['assigned_location_ids'], [self.loc2.get_id])
        self.assertEqual(user_history.changes['location_id'], self.loc2._id)
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_location_replace(self):
        self.setup_locations()

        # first assign to loc1
        create_or_update_commcare_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[self.loc1.site_code])],
            self.uploading_user,
            self.upload_record.pk,
        )

        user_history = UserHistory.objects.get(action=UserModelAction.CREATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc1]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['location_id'], self.loc1._id)
        self.assertEqual(user_history.changes['assigned_location_ids'], [self.loc1.get_id])
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

        # reassign to loc2
        create_or_update_commcare_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[self.loc2.site_code], user_id=self.user._id)],
            self.uploading_user,
            self.upload_record.pk,
        )

        # user's location should now be loc2
        self.assertEqual(self.user.location_id, self.loc2._id)
        self.assert_user_data_item('commcare_location_id', self.loc2._id)
        self.assertListEqual(self.user.assigned_location_ids, [self.loc2._id])

        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               user_id=self.user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc2]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc2))
        change_messages.update(UserChangeMessage.password_reset())
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes['location_id'], self.loc2._id)
        self.assertEqual(user_history.changes['assigned_location_ids'], [self.loc2.get_id])
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    def get_emw_user(self):
        return CommCareUser.get_by_username(
            f'hello@{self.emw_domain.name}.commcarehq.org'
        )

    def test_deactivate_after_updates(self):
        create_or_update_commcare_users_and_groups(
            self.emw_domain.name,
            [self._get_spec(deactivate_after='02-2022')],
            self.uploading_user,
            self.upload_record.pk,
        )
        created_user = self.get_emw_user()
        trigger = DeactivateMobileWorkerTrigger.objects.filter(
            domain=self.emw_domain.name,
            user_id=created_user.user_id
        ).first()
        self.assertEqual(
            trigger.deactivate_after,
            datetime.date(2022, 2, 1)
        )
        user_history = UserHistory.objects.get(
            action=UserModelAction.CREATE.value,
            user_id=created_user.user_id,
            changed_by=self.uploading_user.get_id
        )
        change_messages = {}
        change_messages.update(UserChangeMessage.updated_deactivate_after(
            '02-2022', DeactivateMobileWorkerTriggerUpdateMessage.CREATED
        ))
        self.assertDictEqual(user_history.change_messages, change_messages)

        create_or_update_commcare_users_and_groups(
            self.emw_domain.name,
            [self._get_spec(user_id=created_user.user_id, deactivate_after='03-2022')],
            self.uploading_user,
            self.upload_record.pk,
        )
        created_user = self.get_emw_user()
        trigger = DeactivateMobileWorkerTrigger.objects.filter(
            domain=self.emw_domain.name,
            user_id=created_user.user_id
        ).first()
        self.assertEqual(
            trigger.deactivate_after,
            datetime.date(2022, 3, 1)
        )
        user_history = UserHistory.objects.get(
            action=UserModelAction.UPDATE.value,
            user_id=created_user.user_id,
            changed_by=self.uploading_user.get_id
        )
        change_messages = {}
        change_messages.update(UserChangeMessage.updated_deactivate_after(
            '03-2022', DeactivateMobileWorkerTriggerUpdateMessage.UPDATED
        ))
        change_messages.update(UserChangeMessage.password_reset())
        self.assertDictEqual(user_history.change_messages, change_messages)

        create_or_update_commcare_users_and_groups(
            self.emw_domain.name,
            [self._get_spec(user_id=created_user.user_id, deactivate_after='')],
            self.uploading_user,
            self.upload_record.pk,
        )
        created_user = self.get_emw_user()
        user_history = UserHistory.objects.filter(
            action=UserModelAction.UPDATE.value,
            user_id=created_user.user_id,
            changed_by=self.uploading_user.get_id
        ).last()
        self.assertFalse(DeactivateMobileWorkerTrigger.objects.filter(
            domain=self.emw_domain.name,
            user_id=created_user.user_id
        ).exists())
        change_messages = {}
        change_messages.update(UserChangeMessage.updated_deactivate_after(
            None, DeactivateMobileWorkerTriggerUpdateMessage.DELETED
        ))
        change_messages.update(UserChangeMessage.password_reset())
        self.assertDictEqual(user_history.change_messages, change_messages)

    def test_numeric_user_name(self):
        """
        Test that bulk upload doesn't choke if the user's name is a number
        """
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(name=1234)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(self.user.full_name, "")

    def test_user_data(self):
        self._test_user_data(is_web_upload=False)

    def test_user_data_profile(self):
        self._test_user_data_profile(is_web_upload=False)

    def test_user_data_profile_redundant(self):
        self._test_user_data_profile_redundant(is_web_upload=False)

    def test_user_data_profile_blank(self):
        self._test_user_data_profile_blank(is_web_upload=False)

    def test_required_field_optional_if_profile_set(self):
        self._test_required_field_optional_if_profile_set(is_web_upload=False)

    def test_user_data_profile_conflict(self):
        self._test_user_data_profile_conflict(is_web_upload=False)

    def test_profile_cant_overwrite_existing_data(self):
        self._test_profile_cant_overwrite_existing_data(is_web_upload=False)

    def test_user_data_profile_unknown(self):
        self._test_user_data_profile_unknown(is_web_upload=False)

    def test_uncategorized_data(self):
        self._test_uncategorized_data(is_web_upload=False)

    def test_upper_case_email(self):
        """
        Ensure that bulk upload throws a proper error when the email has caps in it
        """
        email = 'IlOvECaPs@gmaiL.Com'
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(email=email)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(self.user.email, email.lower())

    def test_set_role(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)

    def test_tracking_new_commcare_user(self):
        self.assertEqual(
            UserHistory.objects.filter(
                action=UserModelAction.CREATE.value, changed_by=self.uploading_user.get_id).count(),
            0
        )
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )

        # create
        created_user = self.user
        self.assertEqual(
            LogEntry.objects.filter(action_flag=UserModelAction.CREATE.value).count(),
            0
        )  # deprecated
        user_history = UserHistory.objects.get(action=UserModelAction.CREATE.value,
                                               changed_by=self.uploading_user.get_id)
        self.assertEqual(user_history.by_domain, self.domain.name)
        self.assertEqual(user_history.by_domain, self.domain.name)
        self.assertEqual(user_history.user_type, "CommCareUser")
        self.assertEqual(user_history.user_id, created_user.get_id)
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)
        self.assertEqual(user_history.changes['username'], created_user.username)
        change_messages = UserChangeMessage.role_change(self.role)
        self.assertDictEqual(user_history.change_messages, change_messages)

    def test_tracking_update_to_existing_commcare_user(self):
        CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                            created_by=None, created_via=None)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(
                password="skyfall",
                name="James Bond",
                language='hin',
                email="hello@gmail.org",
                is_active=False,
                data={'post': 'SE'},
                role=self.role.name,
                user_id=self.user._id,
            )],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               changed_by=self.uploading_user.get_id)
        self.assertDictEqual(
            user_history.changes,
            {
                'first_name': 'James',
                'last_name': 'Bond',
                'language': 'hin',
                'email': 'hello@gmail.org',
                'is_active': False,
                'user_data': {'post': 'SE'},
            }
        )
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)
        change_messages = {}
        change_messages.update(UserChangeMessage.password_reset())
        change_messages.update(UserChangeMessage.phone_numbers_added(['23424123']))
        change_messages.update(UserChangeMessage.role_change(self.role))
        self.assertDictEqual(user_history.change_messages, change_messages)

    def test_blank_is_active(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(is_active='')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertTrue(self.user.is_active)

    def test_password_is_not_string(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(password=123)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )['messages']['rows']
        self.user.check_password('123')

    def test_update_user_no_username(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec()],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertIsNotNone(self.user)

        import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id=self.user._id, username='')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )

    def test_update_user_numeric_username(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username=123)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user = self.user
        self.assertIsNotNone(user)
        self.assertEqual(False, user.is_active)
        self.assertEqual(False, user.is_account_confirmed)

    @patch('corehq.apps.user_importer.importer.send_account_confirmation_if_necessary')
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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(mock_account_confirm_email.call_count, 1)
        self.assertEqual('with_email', mock_account_confirm_email.call_args[0][0].raw_username)

    @patch('corehq.apps.user_importer.importer.Invitation.send_activation_email')
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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)

        # only one entry for the mobile worker created
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)
        self.assertEqual(user_history.user_id, self.user.get_id)
        self.assertEqual(user_history.action, UserModelAction.CREATE.value)

    @patch('corehq.apps.user_importer.importer.Invitation')
    def test_upload_add_web_user(self, mock_invitation_class):
        self.loc1 = make_loc('loc1', type='state', domain=self.domain_name)

        username = 'a@a.com'
        web_user = WebUser.create(self.other_domain.name, username, 'password', None, None)
        mock_invite = mock_invitation_class.return_value
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(web_user='a@a.com', is_account_confirmed='True', role=self.role.name,
                            location_code=[self.loc1.site_code])],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        web_user = WebUser.get_by_username(username)
        self.assertFalse(mock_invite.send_activation_email.called)
        self.assertTrue(web_user.is_member_of(self.domain.name))

        # History record for the web user getting added as web user
        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               user_id=web_user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.added_as_web_user(self.domain.name))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        change_messages.update(UserChangeMessage.role_change(self.role))
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes, {})
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    def test_upload_edit_web_user(self):
        username = 'a@a.com'
        web_user = WebUser.create(self.domain.name, username, 'password', None, None)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(web_user='a@a.com', role=self.role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        web_user = WebUser.get_by_username(username)
        self.assertEqual(web_user.get_role(self.domain.name).name, self.role.name)

        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               user_id=web_user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = UserChangeMessage.role_change(self.role)
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes, {})
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    def test_remove_web_user(self):
        username = 'a@a.com'
        web_user = WebUser.create(self.domain.name, username, 'password', None, None)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(web_user='a@a.com', remove_web_user='True')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        web_user = WebUser.get_by_username(username)
        self.assertFalse(web_user.is_member_of(self.domain.name))

        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               user_id=web_user.get_id,
                                               changed_by=self.uploading_user.get_id)
        change_messages = UserChangeMessage.domain_removal(self.domain.name)
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changes, {})
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)

    def test_multi_domain(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username=123, domain=self.other_domain.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        commcare_user = CommCareUser.get_by_username('{}@{}.commcarehq.org'.format('123', self.other_domain.name))
        self.assertIsNotNone(commcare_user)

        # logged under correct domain
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)
        self.assertEqual(user_history.by_domain, self.domain.name)
        self.assertEqual(user_history.for_domain, self.other_domain.name)
        self.assertEqual(user_history.user_id, commcare_user.get_id)
        self.assertEqual(user_history.action, UserModelAction.CREATE.value)

    @patch('corehq.apps.user_importer.importer.Invitation.send_activation_email')
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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)
        self.assertEqual(Invitation.by_email('a@a.com')[0].role.split(":")[1], self.role.get_id)

        # only one entry for mobile user create, none for corresponding web user
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)
        self.assertEqual(user_history.user_id, self.user.get_id)
        self.assertEqual(user_history.action, UserModelAction.CREATE.value)

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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)  # invite only sent once
        self.assertEqual(len(Invitation.by_email('a@a.com')), 1)  # only one invite associated with user
        self.assertEqual(self.user.get_role(self.domain.name).name, self.other_role.name)
        self.assertEqual(Invitation.by_email('a@a.com')[0].role, self.other_role.get_qualified_id())

        # one more added just for commcare user update, none for corresponding web user
        user_historys = list(UserHistory.objects.filter(changed_by=self.uploading_user.get_id))
        self.assertEqual(len(user_historys), 2)
        last_entry = user_historys[1]
        self.assertEqual(last_entry.user_id, self.user.user_id)
        self.assertEqual(last_entry.action, UserModelAction.UPDATE.value)

    def test_ensure_user_history_on_only_userdata_update(self):
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None)
        import_users_and_groups(
            self.domain.name,
            [{'data': {'key': 'F#'}, 'user_id': user._id}],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               changed_by=self.uploading_user.get_id)
        self.assertDictEqual(user_history.changes, {'user_data': {'key': 'F#'}})
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)
        self.assertEqual(user_history.change_messages, {})

    def test_upload_with_phone_number(self):
        user_specs = self._get_spec()
        user_specs['phone-number'] = ['8765547824']

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)

        numbers = user_history.changes['phone_numbers']
        self.assertEqual(numbers, ['8765547824'])

    def test_upload_with_multiple_phone_numbers(self):
        initial_default_number = '12345678912'
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None, phone_number='12345678912')

        number1 = '8765547824'
        number2 = '7765547823'

        user_specs = self._get_spec(delete_keys=['phone-number'], user_id=user._id)
        user_specs['phone-number'] = [number1, number2]

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)

        change_messages = {"phone_numbers": {}}
        change_messages["phone_numbers"].update(
            UserChangeMessage.phone_numbers_added([number1, number2])['phone_numbers']
        )
        change_messages["phone_numbers"].update(
            UserChangeMessage.phone_numbers_removed([initial_default_number])['phone_numbers']
        )
        self.assertEqual(
            set(user_history.change_messages["phone_numbers"]["add_phone_numbers"]["phone_numbers"]),
            set(change_messages["phone_numbers"]["add_phone_numbers"]["phone_numbers"])
        )
        self.assertEqual(
            set(user_history.change_messages["phone_numbers"]["remove_phone_numbers"]["phone_numbers"]),
            set(change_messages["phone_numbers"]["remove_phone_numbers"]["phone_numbers"])
        )

        # Check if user is updated
        users = CommCareUser.by_domain(self.domain.name)
        user = next((u for u in users if u._id == user._id))

        self.assertEqual(user.default_phone_number, number1)
        self.assertEqual(user.phone_numbers, [number1, number2])

    def test_upload_with_multiple_phone_numbers_and_some_blank(self):
        initial_default_number = '12345678912'
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None, phone_number='12345678912')
        number1 = ''
        number2 = '7765547823'

        user_specs = self._get_spec(delete_keys=['phone-number'], user_id=user._id)
        user_specs['phone-number'] = [number1, number2]

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)

        change_messages = {"phone_numbers": {}}
        change_messages["phone_numbers"].update(
            UserChangeMessage.phone_numbers_added([number2])["phone_numbers"]
        )
        change_messages["phone_numbers"].update(
            UserChangeMessage.phone_numbers_removed([initial_default_number])["phone_numbers"]
        )
        change_messages.update(UserChangeMessage.password_reset())
        self.assertDictEqual(user_history.change_messages, change_messages)

        # Check if user is updated
        users = CommCareUser.by_domain(self.domain.name)
        user = next((u for u in users if u._id == user._id))

        self.assertEqual(user.default_phone_number, number2)
        self.assertEqual(user.phone_numbers, [number2])

    def test_upload_with_multiple_phone_numbers_with_duplicates(self):
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None, phone_number='12345678912')
        number1 = '7765547823'
        duplicate_number = number1

        user_specs = self._get_spec(delete_keys=['phone-number'], user_id=user._id)
        user_specs['phone-number'] = [number1, duplicate_number]

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)

        change_messages = {"phone_numbers": {}}
        change_messages["phone_numbers"].update(
            UserChangeMessage.phone_numbers_added([number1])["phone_numbers"]
        )
        change_messages["phone_numbers"].update(
            UserChangeMessage.phone_numbers_removed(["12345678912"])["phone_numbers"]
        )
        change_messages.update(UserChangeMessage.password_reset())
        self.assertDictEqual(user_history.change_messages, change_messages)

        # Check if user is updated
        users = CommCareUser.by_domain(self.domain.name)
        user = next((u for u in users if u._id == user._id))

        self.assertEqual(user.default_phone_number, number1)
        self.assertEqual(user.phone_numbers, [number1])

    def test_upload_with_badly_formatted_phone_numbers(self):
        number1 = '+27893224921'
        bad_number = '2o34532445665'

        user_specs = self._get_spec(delete_keys=['phone-number'])
        user_specs['phone-number'] = [number1, bad_number]

        res = import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )

        self.assertEqual(res['messages']['rows'][0]['flag'], f'Invalid phone number detected: {bad_number}')

    def test_upload_with_no_phone_numbers(self):
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None, phone_number='12345678912')

        user_specs = self._get_spec(delete_keys=['phone-number'], user_id=user._id)
        user_specs['phone-number'] = []

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)
        change_messages = {}
        change_messages.update(UserChangeMessage.phone_numbers_removed(['12345678912']))
        change_messages.update(UserChangeMessage.password_reset())
        self.assertDictEqual(user_history.change_messages, change_messages)

        # Check if user is updated
        users = CommCareUser.by_domain(self.domain.name)
        user = next((u for u in users if u._id == user._id))

        self.assertEqual(user.default_phone_number, None)
        self.assertEqual(user.phone_number, None)
        self.assertEqual(user.phone_numbers, [])

    def test_upload_with_no_phone_number_in_row(self):
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None, phone_number='12345678912')

        user_specs = self._get_spec(delete_keys=['phone-number'], user_id=user._id)

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)
        # assert no phone number change
        self.assertFalse("phone_numbers" in user_history.change_messages)

        # Check if user is updated
        users = CommCareUser.by_domain(self.domain.name)
        user = next((u for u in users if u._id == user._id))

        self.assertEqual(user.default_phone_number, '12345678912')
        self.assertEqual(user.phone_number, '12345678912')
        self.assertEqual(user.phone_numbers, ['12345678912'])

    def test_upload_with_group(self):
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None)
        user_specs = self._get_spec(user_id=user._id)
        group = Group(domain=self.domain.name, name="test_group")
        group.save()

        self.addCleanup(group.delete)

        user_specs['group'] = ["test_group"]

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [{'id': group._id, 'name': 'test_group', 'case-sharing': False, 'reporting': True}],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )

        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)

        self.assertEqual(user_history.change_messages['groups'],
            UserChangeMessage.groups_info([group])['groups'])

    def test_upload_with_no_group(self):
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None)
        user_specs = self._get_spec(user_id=user._id)
        group = Group(domain=self.domain.name, name="test_group")
        group.save()
        group.add_user(user._id)

        self.addCleanup(group.delete)

        user_specs['group'] = []

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )

        user_history = UserHistory.objects.get(changed_by=self.uploading_user.get_id)

        self.assertEqual(user_history.change_messages['groups'],
            UserChangeMessage.groups_info([])['groups'])

    def test_upload_new_group(self):
        import_users_and_groups(
            self.domain.name,
            [],
            [{'id': '', 'name': 'test_group', 'case-sharing': False, 'reporting': False}],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        groups = Group.by_domain(self.domain.name)
        self.assertEqual(len(groups), 1)

    def test_upload_group_changes(self):
        group = Group(domain=self.domain.name, name="test_group")
        group.save()

        import_users_and_groups(
            self.domain.name,
            [],
            [{'id': group._id, 'name': 'another_group', 'case-sharing': False, 'reporting': False}],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        updated_group = Group.get(group._id)
        self.assertEqual(updated_group.name, 'another_group')

    def test_upload_new_group_and_assign_to_user(self):
        user = CommCareUser.create(self.domain_name, f"hello@{self.domain.name}.commcarehq.org", "*******",
                                   created_by=None, created_via=None)
        user_specs = self._get_spec(user_id=user._id, group=['test_group'])

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [{'id': '', 'name': 'test_group', 'case-sharing': False, 'reporting': False}],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        groups = user.get_group_ids()
        self.assertEqual(len(groups), 1)

    def test_upload_new_group_and_assign_to_new_user(self):
        user_specs = self._get_spec(group=['test_group'])

        import_users_and_groups(
            self.domain.name,
            [user_specs],
            [{'id': '', 'name': 'test_group', 'case-sharing': False, 'reporting': False}],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )
        groups = self.user.get_group_ids()
        self.assertEqual(len(groups), 1)

    def test_create_or_update_commcare_users_and_groups_with_bad_username(self):
        result = create_or_update_commcare_users_and_groups(
            self.domain.name,
            [self._get_spec(username="..bad username")],
            self.uploading_user,
            self.upload_record.pk,
        )
        self.assertEqual(
            result["rows"][0]["flag"],
            "Username must not contain blank spaces or special characters."
        )


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
        cls.upload_record = UserUploadRecord(
            domain=cls.domain_name,
            user_id=cls.uploading_user.get_id
        )
        cls.upload_record.save()

    @classmethod
    def tearDownClass(cls):
        cls.upload_record.delete()
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
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'], "'password' values must be unique")

    @disable_extensions('corehq.apps.domain.extension_points.validate_password_rules')
    @override_settings(MINIMUM_PASSWORD_LENGTH=8)
    def test_weak_password(self):
        updated_user_spec = deepcopy(self.user_specs[0])
        updated_user_spec["password"] = '123'

        rows = import_users_and_groups(
            self.domain.name,
            list([updated_user_spec]),
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            False
        )['messages']['rows']
        self.assertEqual(rows[0]['flag'],
        _("Password must have at least 8 characters."))


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
            user_id=self.uploading_user.get_id
        )
        upload_record.save()
        self.addCleanup(upload_record.delete)

        task_result = import_users_and_groups.si(
            self.domain.name,
            [self.spec],
            [],
            self.uploading_user.get_id,
            upload_record.pk,
            False
        ).apply()
        rows = task_result.result

        upload_record.refresh_from_db()
        self.assertEqual(rows['messages'], upload_record.result)


class TestWebUserBulkUpload(TestCase, DomainSubscriptionMixin, TestUserDataMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()
        cls.domain_name = 'mydomain'
        cls.domain = Domain.get_or_create_with_name(name=cls.domain_name)
        cls.other_domain = Domain.get_or_create_with_name(name='other-domain')
        cls.role = UserRole.create(cls.domain.name, 'edit-apps')
        cls.other_role = UserRole.create(cls.domain.name, 'admin')
        cls.other_domain_role = UserRole.create(cls.other_domain.name, 'view-apps')
        create_enterprise_permissions("a@a.com", cls.domain_name, [cls.other_domain.name])
        cls.patcher = patch('corehq.apps.user_importer.tasks.UserUploadRecord')
        cls.patcher.start()

        cls.upload_record = UserUploadRecord(
            domain=cls.domain_name,
            user_id=1,
        )
        cls.upload_record.save()
        cls.setup_userdata()

    @classmethod
    def tearDownClass(cls):
        cls.upload_record.delete()
        cls.domain.delete()
        cls.other_domain.delete()
        cls.patcher.stop()
        cls.tear_down_user_data()
        super().tearDownClass()

    def tearDown(self):
        Invitation.objects.all().delete()
        delete_all_users()

    def setUp(self):
        method = getattr(self, self._testMethodName)
        tags = getattr(method, 'tags', {})
        if 'skip_setup_users' in tags:
            return
        self.setup_users()

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
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(role='')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertIsNone(self.user_invite)

    def test_upload_existing_web_user(self):
        web_user = WebUser.create(self.other_domain.name, 'existing@user.com', 'abc', None, None,
                                  email='existing@user.com')
        self.assertIsNone(Invitation.objects.filter(email='existing@user.com').first())
        import_users_and_groups(
            self.domain.name,
            [{'username': 'existing@user.com',
              'status': 'Active User',
              'email': 'existing@user.com',
              'role': self.role.name}],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertIsNotNone(Invitation.objects.filter(email='existing@user.com').first())
        user_history = UserHistory.objects.get(
            user_id=web_user.get_id, changed_by=self.uploading_user.get_id, action=UserModelAction.UPDATE.value
        )
        self.assertEqual(user_history.by_domain, self.domain.name)
        self.assertEqual(user_history.for_domain, self.domain.name)
        change_messages = UserChangeMessage.invited_to_domain(self.domain.name)
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)
        self.assertEqual(user_history.changes, {})

    def test_web_user_user_name_change(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(first_name='', last_name='')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        # should not be changed
        self.assertNotEqual(self.user.first_name, "")
        self.assertNotEqual(self.user.last_name, "")

        user_history = UserHistory.objects.get()
        self.assertNotIn('first_name', user_history.changes)
        self.assertNotIn('last_name', user_history.changes)

    def test_upper_case_email(self):
        email = 'hELlo@WoRld.Com'
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(email=email)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(self.user.email, email.lower())

        # no change recorded for email
        user_history = UserHistory.objects.get()
        self.assertNotIn('email', user_history.changes)

    def test_user_data(self):
        self._test_user_data(is_web_upload=True)

    def test_user_data_profile(self):
        self._test_user_data_profile(is_web_upload=True)

    def test_user_data_profile_redundant(self):
        self._test_user_data_profile_redundant(is_web_upload=True)

    def test_user_data_profile_blank(self):
        self._test_user_data_profile_blank(is_web_upload=True)

    def test_required_field_optional_if_profile_set(self):
        self._test_required_field_optional_if_profile_set(is_web_upload=True)

    def test_user_data_profile_conflict(self):
        self._test_user_data_profile_conflict(is_web_upload=True)

    def test_profile_cant_overwrite_existing_data(self):
        self._test_profile_cant_overwrite_existing_data(is_web_upload=True)

    def test_user_data_profile_unknown(self):
        self._test_user_data_profile_unknown(is_web_upload=True)

    def test_uncategorized_data(self):
        self._test_uncategorized_data(is_web_upload=True)

    def test_user_data_ignores_location_fields(self):
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(data={'key': 'F#'}, location_code=self.loc1.site_code)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assert_user_data_excludes([
            'commcare_location_id',
            'commcare_location_ids',
            'commcare_primary_case_sharing_id',
        ])

        import_users_and_groups(
            self.domain.name,
            [self._get_spec(user_id=self.user.user_id, data={'key': 'G#'}, location_code=self.loc1.site_code)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assert_user_data_excludes([
            'commcare_location_id',
            'commcare_location_ids',
            'commcare_primary_case_sharing_id',
        ])

    def test_set_role(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)
        user_history = UserHistory.objects.get(
            changed_by=self.uploading_user.get_id, action=UserModelAction.UPDATE.value
        )
        change_messages = UserChangeMessage.role_change(self.role)
        self.assertDictEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)
        self.assertEqual(user_history.changes, {})

    def test_update_role_current_user(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.role.name)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(role=self.other_role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(self.user.get_role(self.domain_name).name, self.other_role.name)

    def test_update_role_invited_user(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(role=self.role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(self.user_invite.get_role_name(), self.role.name)

        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(role=self.other_role.name)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(self.user_invite.get_role_name(), self.other_role.name)

    def test_remove_user(self):
        username = 'a@a.com'
        WebUser.create(self.domain.name, username, 'password', None, None)
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username='a@a.com', remove='True')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        web_user = WebUser.get_by_username(username)
        self.assertFalse(web_user.is_member_of(self.domain.name))
        self.assertIsNone(Invitation.objects.filter(domain=self.domain_name, email=username).first())

        user_history = UserHistory.objects.filter(
            user_id=web_user.get_id, changed_by=self.uploading_user.get_id, action=UserModelAction.UPDATE.value
        ).last()
        change_messages = UserChangeMessage.domain_removal(self.domain.name)
        self.assertDictEqual(user_history.change_messages, change_messages)

    def test_remove_invited_user(self):
        Invitation.objects.all().delete()
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec()],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertIsNotNone(self.user_invite)
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(remove='True')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertIsNone(self.user_invite)

    def test_remove_uploading_user(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username=self.uploading_user.username, remove='True')],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        web_user = WebUser.get_by_username(self.uploading_user.username)
        self.assertTrue(web_user.is_member_of(self.domain.name))

    @patch('corehq.apps.user_importer.importer.Invitation.send_activation_email')
    def test_upload_invite(self, mock_send_activation_email):
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec()],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(mock_send_activation_email.call_count, 1)

    def test_multi_domain(self):
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(username='123@email.com',
                            domain=self.other_domain.name,
                            role=self.other_domain_role.name,
                            email='123@email.com'
                            )],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertIsNotNone(Invitation.objects.filter(email='123@email.com').first())
        self.assertEqual(Invitation.objects.filter(email='123@email.com').first().domain, self.other_domain.name)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_web_user_location_add(self):
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        membership = self.user.get_domain_membership(self.domain_name)
        # test that first location should be primary location
        self.assertEqual(membership.location_id, self.loc1._id)
        # test for multiple locations
        self.assertListEqual([loc._id for loc in [self.loc1, self.loc2]], membership.assigned_location_ids)

        user_history = UserHistory.objects.get()
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc1, self.loc2]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        change_messages.update(UserChangeMessage.role_change(self.role))
        self.assertDictEqual(user_history.change_messages, change_messages)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_web_user_location_remove(self):
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[a.site_code for a in [self.loc1, self.loc2]])],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )

        user_history = UserHistory.objects.get()
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([self.loc1, self.loc2]))
        change_messages.update(UserChangeMessage.primary_location_info(self.loc1))
        change_messages.update(UserChangeMessage.role_change(self.role))
        self.assertDictEqual(user_history.change_messages, change_messages)

        import_users_and_groups(
            self.domain.name,
            [self._get_spec(location_code=[], user_id=self.user._id)],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        membership = self.user.get_domain_membership(self.domain_name)
        self.assertEqual(membership.location_id, None)
        self.assertListEqual(membership.assigned_location_ids, [])
        user_history = UserHistory.objects.filter(user_id=self.user.get_id).last()
        change_messages = {}
        change_messages.update(UserChangeMessage.assigned_locations_info([]))
        change_messages.update(UserChangeMessage.primary_location_info(None))
        self.assertDictEqual(user_history.change_messages, change_messages)

    @patch('corehq.apps.user_importer.importer.domain_has_privilege', lambda x, y: True)
    def test_invite_location_add(self):
        self.setup_locations()
        import_users_and_groups(
            self.domain.name,
            [self._get_invited_spec(location_code=[a.site_code for a in [self.loc1]])],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(self.user_invite.location_id, self.loc1._id)

    def setup_locations(self):
        self.loc1 = make_loc('loc1', type='state', domain=self.domain_name)
        self.loc2 = make_loc('loc2', type='state', domain=self.domain_name)

    def _setup_tableau_users(self):
        self.setup_users()
        WebUser.create(
            self.domain.name,
            'edith@wharton.com',
            'badpassword',
            None,
            None,
        )
        WebUser.create(
            self.domain.name,
            'george@eliot.com',
            'badpassword',
            None,
            None,
        )

    def _mock_create_user_mock_responses(self, username):
        return _mock_create_session_responses(self) + [
            self.tableau_instance.create_user_response(username, None),
            self.tableau_instance.get_group_response(HQ_TABLEAU_GROUP_NAME),
            self.tableau_instance.add_user_to_group_response()]

    def _mock_update_user_responses(self, username):
        return [
            self.tableau_instance.get_groups_for_user_id_response(),
            self.tableau_instance.delete_user_response(),
            self.tableau_instance.create_user_response(username, None),
            self.tableau_instance.get_group_response(HQ_TABLEAU_GROUP_NAME),
            self.tableau_instance.add_user_to_group_response(),
            self.tableau_instance.add_user_to_group_response(),
            self.tableau_instance.add_user_to_group_response()
        ]

    @tag('skip_setup_users')
    @flag_enabled('TABLEAU_USER_SYNCING')
    @patch('corehq.apps.reports.models.requests.request')
    def test_tableau_users(self, mock_request):
        _setup_test_tableau_server(self, self.domain_name)
        mock_request.side_effect = (self._mock_create_user_mock_responses('hello@world.com')
            + self._mock_create_user_mock_responses('upload@user.com')
            + self._mock_create_user_mock_responses('edith@wharton.com')
            + self._mock_create_user_mock_responses('george@eliot.com')
            + _mock_create_session_responses(self)
            + [self.tableau_instance.get_group_response('group1'),
               self.tableau_instance.get_group_response('group2')]
            + self._mock_update_user_responses('edith@wharton.com')
            + [self.tableau_instance.delete_user_response()]
        )
        self._setup_tableau_users()
        local_tableau_users = TableauUser.objects.filter(
            server=TableauServer.objects.get(domain=self.domain_name))
        self.assertEqual(local_tableau_users.get(username='edith@wharton.com').role,
            TableauUser.Roles.UNLICENSED.value)
        local_tableau_users.get(username='george@eliot.com')
        import_users_and_groups(
            self.domain.name,
            [
                self._get_spec(
                    username='edith@wharton.com',
                    tableau_role=TableauUser.Roles.EXPLORER.value,
                    tableau_groups="""group1,group2"""
                ),
                self._get_spec(
                    username='hello@world.com',
                    tableau_role=TableauUser.Roles.EXPLORER.value,
                    tableau_groups='ERROR'
                ),
                self._get_spec(
                    username='george@eliot.com',
                    remove='1',
                    tableau_groups='[]'
                ),
            ],
            [],
            self.uploading_user.get_id,
            self.upload_record.pk,
            True
        )
        self.assertEqual(local_tableau_users.get(username='edith@wharton.com').role,
            TableauUser.Roles.EXPLORER.value)
        # Role shouldn't have changed since there was an ERROR in the tableau_groups column
        self.assertEqual(local_tableau_users.get(username='hello@world.com').role,
            TableauUser.Roles.UNLICENSED.value)
        with self.assertRaises(TableauUser.DoesNotExist):
            local_tableau_users.get(username='george@eliot.com')


@patch_user_data_db_layer()
class TestUserChangeLogger(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_name = 'mydomain'
        cls.uploading_user = WebUser(username="admin@xyz.com")
        cls.upload_record = UserUploadRecord(
            domain=cls.domain_name,
            user_id=cls.uploading_user.get_id
        )

    def test_add_change_message_duplicate_slug_entry(self):
        user = CommCareUser()
        user_change_logger = UserChangeLogger(
            upload_domain=self.domain_name,
            user_domain=self.domain_name,
            user=user,
            is_new_user=True,
            changed_by_user=self.uploading_user,
            changed_via=USER_CHANGE_VIA_BULK_IMPORTER,
            upload_record_id=1
        )
        user_change_logger.add_change_message(UserChangeMessage.password_reset())

        # no change noted for new user
        self.assertEqual(user_change_logger.change_messages, {})

        # no exception raised for new user
        user_change_logger.add_change_message(UserChangeMessage.password_reset())

        user_change_logger = UserChangeLogger(
            upload_domain=self.domain_name,
            user_domain=self.domain_name,
            user=user,
            is_new_user=False,
            changed_by_user=self.uploading_user,
            changed_via=USER_CHANGE_VIA_BULK_IMPORTER,
            upload_record_id=self.upload_record.pk
        )
        user_change_logger.add_change_message(UserChangeMessage.password_reset())

        self.assertEqual(user_change_logger.change_messages, UserChangeMessage.password_reset())

        with self.assertRaisesMessage(UserUploadError, "Double Entry for password"):
            user_change_logger.add_change_message(UserChangeMessage.password_reset())

    def test_add_info_duplicate_slug_entry(self):
        user = CommCareUser()
        user_change_logger = UserChangeLogger(
            upload_domain=self.domain_name,
            user_domain=self.domain_name,
            user=user,
            is_new_user=True,
            changed_by_user=self.uploading_user,
            changed_via=USER_CHANGE_VIA_BULK_IMPORTER,
            upload_record_id=self.upload_record.pk
        )
        user_change_logger.add_info(UserChangeMessage.program_change(None))

        self.assertEqual(user_change_logger.change_messages, UserChangeMessage.program_change(None))

        with self.assertRaisesMessage(UserUploadError, "Double Entry for program"):
            user_change_logger.add_info(UserChangeMessage.program_change(None))

        user_change_logger = UserChangeLogger(
            upload_domain=self.domain_name,
            user_domain=self.domain_name,
            user=user,
            is_new_user=False,
            changed_by_user=self.uploading_user,
            changed_via=USER_CHANGE_VIA_BULK_IMPORTER,
            upload_record_id=self.upload_record.pk
        )
        user_change_logger.add_info(UserChangeMessage.program_change(None))

        self.assertEqual(user_change_logger.change_messages, UserChangeMessage.program_change(None))

        with self.assertRaisesMessage(UserUploadError, "Double Entry for program"):
            user_change_logger.add_info(UserChangeMessage.program_change(None))
