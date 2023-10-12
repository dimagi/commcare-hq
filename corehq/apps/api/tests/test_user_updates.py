from django.test import TestCase
from django.core.exceptions import ValidationError

from corehq.apps.api.exceptions import UpdateUserException
from corehq.apps.api.user_updates import update
from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.user_importer.helpers import UserChangeLogger
from corehq.apps.users.audit.change_messages import (
    GROUPS_FIELD,
    PASSWORD_FIELD,
    ROLE_FIELD,
)
from corehq.apps.users.models import CommCareUser, HqPermissions
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.views.mobile import UserFieldsView
from corehq.const import USER_CHANGE_VIA_API


class TestUpdateUserMethods(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def setUp(self) -> None:
        super().setUp()
        self.user = CommCareUser.create('test-domain', 'test-username', 'qwer1234', None, None)
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

    def test_update_password_without_strong_passwords_succeeds(self):
        self.domain_obj.strong_mobile_passwords = False
        self.domain_obj.save()

        update(self.user, 'password', 'abc123')  # should not raise

    def test_update_password_with_strong_passwords_raises_exception(self):
        self.domain_obj.strong_mobile_passwords = True
        self.domain_obj.save()

        with self.assertRaises(UpdateUserException) as cm:
            update(self.user, 'password', 'abc123')

        self.assertEqual(cm.exception.message, "Password is not strong enough.")

    def test_update_password_with_strong_passwords_succeeds(self):
        self.domain_obj.strong_mobile_passwords = True
        self.domain_obj.save()

        update(self.user, 'password', 'a7d8fhjkdf8d')  # should not raise

    def test_update_email_succeeds(self):
        self.user.email = 'initial@dimagi.com'
        update(self.user, 'email', 'updated@dimagi.com')
        self.assertEqual(self.user.email, 'updated@dimagi.com')

    def test_update_first_name_succeeds(self):
        self.user.first_name = 'Initial'
        update(self.user, 'first_name', 'Updated')
        self.assertEqual(self.user.first_name, 'Updated')

    def test_update_last_name_succeeds(self):
        self.user.last_name = 'Initial'
        update(self.user, 'last_name', 'Updated')
        self.assertEqual(self.user.last_name, 'Updated')

    def test_update_language_succeeds(self):
        self.user.language = 'in'
        update(self.user, 'language', 'up')
        self.assertEqual(self.user.language, 'up')

    def test_update_default_phone_number_succeeds(self):
        self.user.set_default_phone_number('50253311398')
        update(self.user, 'default_phone_number', '50253311399')
        self.assertEqual(self.user.default_phone_number, '50253311399')

    def test_update_default_phone_number_preserves_previous_number(self):
        self.user.set_default_phone_number('50253311398')
        update(self.user, 'default_phone_number', '50253311399')
        self.assertIn('50253311398', self.user.phone_numbers)

    def test_update_default_phone_number_raises_exception_if_not_string(self):
        self.user.set_default_phone_number('50253311398')
        with self.assertRaises(UpdateUserException) as cm:
            update(self.user, 'default_phone_number', 50253311399)

        self.assertEqual(cm.exception.message, "'default_phone_number' must be a string")

    def test_update_phone_numbers_succeeds(self):
        self.user.phone_numbers = ['50253311398']
        update(self.user, 'phone_numbers', ['50253311399', '50253311398'])
        self.assertEqual(self.user.phone_numbers, ['50253311399', '50253311398'])

    def test_update_phone_numbers_updates_default(self):
        self.user.set_default_phone_number('50253311398')
        update(self.user, 'phone_numbers', ['50253311399', '50253311398'])
        self.assertEqual(self.user.default_phone_number, '50253311399')

    def test_update_user_data_succeeds(self):
        self.user.get_user_data(self.domain)['custom_data'] = "initial custom data"
        update(self.user, 'user_data', {'custom_data': 'updated custom data'})
        self.assertEqual(self.user.get_user_data(self.domain)["custom_data"], "updated custom data")

    def test_update_user_data_raises_exception_if_profile_conflict(self):
        profile_id = self._setup_profile()
        with self.assertRaises(UpdateUserException) as cm:
            update(self.user, 'user_data', {PROFILE_SLUG: profile_id, 'conflicting_field': 'no'})
        self.assertEqual(cm.exception.message, "'conflicting_field' cannot be set directly")

    def test_profile_not_found(self):
        with self.assertRaises(UpdateUserException) as cm:
            update(self.user, 'user_data', {PROFILE_SLUG: 123456})
        self.assertEqual(cm.exception.message, "User data profile not found")

    def test_update_groups_succeeds(self):
        group = Group({"name": "test", "domain": self.user.domain})
        group.save()
        self.addCleanup(group.delete)
        update(self.user, 'groups', [group._id])
        self.assertEqual(self.user.get_group_ids()[0], group._id)

    def test_update_groups_fails(self):
        group = Group({"name": "test", "domain": "not-same-domain"})
        group.save()
        self.addCleanup(group.delete)
        with self.assertRaises(ValidationError):
            update(self.user, 'groups', [group._id])

    def test_update_unknown_field_raises_exception(self):
        with self.assertRaises(UpdateUserException) as cm:
            update(self.user, 'username', 'new-username')

        self.assertEqual(cm.exception.message, "Attempted to update unknown or non-editable field 'username'")

    def test_update_user_role_succeeds(self):
        new_role = UserRole.create(
            self.domain, 'edit-data', permissions=HqPermissions(edit_data=True)
        )
        update(self.user, 'role', 'edit-data')
        self.assertEqual(self.user.get_role(self.domain).get_qualified_id(), new_role.get_qualified_id())

    def test_update_user_role_raises_exception_if_does_not_exist(self):
        with self.assertRaises(UpdateUserException) as cm:
            update(self.user, 'role', 'edit-data')

        self.assertEqual(cm.exception.message, "The role 'edit-data' does not exist")

    def test_update_user_role_raises_exception_if_ambiguous(self):
        UserRole.create(
            self.domain, 'edit-data', permissions=HqPermissions(edit_data=True)
        )
        UserRole.create(
            self.domain, 'edit-data', permissions=HqPermissions(edit_data=True)
        )

        with self.assertRaises(UpdateUserException) as cm:
            update(self.user, 'role', 'edit-data')

        self.assertEqual(
            cm.exception.message,
            "There are multiple roles with the name 'edit-data' in the domain 'test-domain'"
        )

    def _setup_profile(self):
        definition = CustomDataFieldsDefinition(domain=self.domain,
                                                field_type=UserFieldsView.field_type)
        definition.save()
        definition.set_fields([
            Field(
                slug='conflicting_field',
                label='Conflicting Field',
                choices=['yes', 'no'],
            ),
        ])
        definition.save()
        profile = CustomDataFieldsProfile(
            name='character',
            fields={'conflicting_field': 'yes'},
            definition=definition,
        )
        profile.save()
        return profile.id


class TestUpdateUserMethodsLogChanges(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def setUp(self) -> None:
        super().setUp()
        self.user = CommCareUser.create('test-domain', 'test-username', 'qwer1234', None, None)
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

        self.user_change_logger = UserChangeLogger(
            upload_domain=self.domain,
            user_domain=self.domain,
            user=self.user,
            is_new_user=False,
            changed_by_user=self.user,
            changed_via=USER_CHANGE_VIA_API,
            upload_record_id=None,
            user_domain_required_for_log=True
        )

    def test_update_password_logs_change(self):
        update(self.user, 'password', 'a7d8fhjkdf8d', user_change_logger=self.user_change_logger)
        self.assertIn(PASSWORD_FIELD, self.user_change_logger.change_messages.keys())

    def test_update_email_logs_change(self):
        self.user.email = 'initial@dimagi.com'
        update(self.user, 'email', 'updated@dimagi.com', user_change_logger=self.user_change_logger)
        self.assertIn('email', self.user_change_logger.fields_changed.keys())

    def test_update_email_with_no_change_does_not_log_change(self):
        self.user.email = 'unchanged@dimagi.com'
        update(self.user, 'email', 'unchanged@dimagi.com', user_change_logger=self.user_change_logger)
        self.assertNotIn('email', self.user_change_logger.fields_changed.keys())

    def test_update_first_name_logs_change(self):
        self.user.first_name = 'Initial'
        self.user.save()
        update(self.user, 'first_name', 'Updated', user_change_logger=self.user_change_logger)
        self.assertIn('first_name', self.user_change_logger.fields_changed.keys())

    def test_update_first_name_does_not_log_no_change(self):
        self.user.first_name = 'Unchanged'
        update(self.user, 'first_name', 'Unchanged', user_change_logger=self.user_change_logger)
        self.assertNotIn('first_name', self.user_change_logger.fields_changed.keys())

    def test_update_last_name_logs_change(self):
        self.user.last_name = 'Initial'
        update(self.user, 'last_name', 'Updated', user_change_logger=self.user_change_logger)
        self.assertIn('last_name', self.user_change_logger.fields_changed.keys())

    def test_update_last_name_does_not_log_no_change(self):
        self.user.last_name = 'Unchanged'
        update(self.user, 'last_name', 'Unchanged', user_change_logger=self.user_change_logger)
        self.assertNotIn('last_name', self.user_change_logger.fields_changed.keys())

    def test_update_language_logs_change(self):
        self.user.language = 'in'
        update(self.user, 'language', 'up', user_change_logger=self.user_change_logger)
        self.assertIn('language', self.user_change_logger.fields_changed.keys())

    def test_update_language_does_not_log_no_change(self):
        self.user.language = 'un'
        update(self.user, 'language', 'un', user_change_logger=self.user_change_logger)
        self.assertNotIn('language', self.user_change_logger.fields_changed.keys())

    def test_update_default_phone_number_logs_change(self):
        self.user.set_default_phone_number('50253311398')
        update(self.user, 'default_phone_number', '50253311399', user_change_logger=self.user_change_logger)
        self.assertIn('phone_numbers', self.user_change_logger.change_messages.keys())

    def test_update_default_phone_number_does_not_log_no_change(self):
        self.user.set_default_phone_number('50253311399')
        update(self.user, 'default_phone_number', '50253311399', user_change_logger=self.user_change_logger)
        self.assertNotIn('phone_numbers', self.user_change_logger.change_messages.keys())

    def test_update_phone_numbers_logs_changes(self):
        self.user.phone_numbers = ['50253311398']
        update(self.user, 'phone_numbers', ['50253311399'], user_change_logger=self.user_change_logger)
        self.assertIn('phone_numbers', self.user_change_logger.change_messages.keys())

    def test_update_phone_numbers_does_not_log_no_change(self):
        self.user.phone_numbers = ['50253311399', '50253311398']

        update(self.user,
               'phone_numbers',
               ['50253311399', '50253311398'],
               user_change_logger=self.user_change_logger)

        self.assertNotIn('phone_numbers', self.user_change_logger.change_messages.keys())

    def test_update_user_data_logs_change(self):
        self.user.get_user_data(self.domain)['custom_data'] = "initial custom data"

        update(self.user,
               'user_data',
               {'custom_data': 'updated custom data'},
               user_change_logger=self.user_change_logger)

        self.assertIn('user_data', self.user_change_logger.fields_changed.keys())

    def test_update_user_data_does_not_log_no_change(self):
        self.user.get_user_data(self.domain)['custom_data'] = "unchanged custom data"
        update(self.user, 'user_data', {'custom_data': 'unchanged custom data'})
        self.assertNotIn('user_data', self.user_change_logger.fields_changed.keys())

    def test_update_groups_logs_change(self):
        group = Group({"name": "test", "domain": self.user.domain})
        group.save()
        self.addCleanup(group.delete)
        update(self.user, 'groups', [group._id], user_change_logger=self.user_change_logger)
        self.assertIn(GROUPS_FIELD, self.user_change_logger.change_messages.keys())

    def test_update_groups_does_not_log_no_change(self):
        group = Group({"name": "test", "domain": self.user.domain})
        group.save()
        self.user.set_groups([group._id])
        self.addCleanup(group.delete)
        update(self.user, 'groups', [group._id], user_change_logger=self.user_change_logger)
        self.assertNotIn(GROUPS_FIELD, self.user_change_logger.change_messages.keys())

    def test_update_user_role_logs_change(self):
        UserRole.create(
            self.domain, 'edit-data', permissions=HqPermissions(edit_data=True)
        )
        update(self.user, 'role', 'edit-data', user_change_logger=self.user_change_logger)
        self.assertIn(ROLE_FIELD, self.user_change_logger.change_messages.keys())

    def test_update_user_role_does_not_logs_change(self):
        role = UserRole.create(
            self.domain, 'edit-data', permissions=HqPermissions(edit_data=True)
        )
        self.user.set_role(self.domain, role.get_qualified_id())

        update(self.user, 'role', 'edit-data', user_change_logger=self.user_change_logger)

        self.assertNotIn(ROLE_FIELD, self.user_change_logger.change_messages.keys())
