from datetime import datetime
from unittest.mock import patch

import pytest
from django.test import TestCase
from faker import Faker
from testil import assert_raises

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import LocationHierarchyTestCase, restrict_user_by_location
from corehq.apps.reports.models import TableauUser, TableauServer
from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.importer import SiteCodeToLocationCache
from corehq.apps.user_importer.validation import (
    DuplicateValidator,
    EmailValidator,
    ExistingUserValidator,
    GroupValidator,
    UsernameLengthValidator,
    NewUserPasswordValidator,
    ProfileValidator,
    RoleValidator,
    UsernameTypeValidator,
    RequiredFieldsValidator,
    UsernameValidator,
    BooleanColumnValidator,
    ConfirmationSmsValidator,
    LocationValidator,
    _get_invitation_or_editable_user,
    CustomDataValidator,
    TableauRoleValidator,
    TableauGroupsValidator,
)
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, HqPermissions, Invitation, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field)
from corehq.apps.users.views.mobile.custom_data_fields import (
    UserFieldsView,
    WebUserFieldsView,
    CommcareUserFieldsView,
)
from corehq.tests.tools import nottest
from corehq.util.test_utils import flag_enabled

factory = Faker()
Faker.seed(1571040848)

IsActiveValidator = BooleanColumnValidator('domain', 'is_active')
IsAccountConfirmedValidator = BooleanColumnValidator('domain', 'is_account_confirmed')

# tuple(specs, validator class, errors dict(row_index: message)
TEST_CASES = [
    (
        [
            {'username': 'jack black <email'},
            {'username': factory.user_name()},
            {'username': ''},
            {},
        ],
        UsernameValidator('domain'),
        {0: UsernameValidator.error_message}
    ),
    (
        [
            {'is_active': 'true'},
            {'is_active': 'false'},
            {'is_active': 'active'},
            {'is_active': ''},
            {},
        ],
        IsActiveValidator,
        {2: IsActiveValidator.error_message}
    ),
    (
        [
            {'is_account_confirmed': 'true'},
            {'is_account_confirmed': 'false'},
            {'is_account_confirmed': 'confirmed'},
            {'is_account_confirmed': ''},
            {},
        ],
        IsAccountConfirmedValidator,
        {2: IsAccountConfirmedValidator.error_message}
    ),
    (
        [
            {'username': factory.user_name()},
            {'user_id': factory.uuid4()},
            {}
        ],
        RequiredFieldsValidator('domain'),
        {2: RequiredFieldsValidator.error_message}
    ),
    (
        [
            {'username': 'verylongusernamelessthan30char'},
            {'username': 'verylongusernamemorethan30chars'}
        ],
        UsernameLengthValidator('domain', 30),
        {1: UsernameLengthValidator._error_message.format(length=30)}
    ),
    (
        [
            {'username': factory.user_name()},
            {'username': factory.user_name(), 'user_id': factory.uuid4()},
            {'username': factory.user_name(), 'password': factory.password()},
            {'username': factory.user_name(), 'password': 123},
            {'username': factory.user_name(), 'is_account_confirmed': 'False'},
            {'username': factory.user_name(), 'is_account_confirmed': 'True'},
            {'username': factory.user_name(), 'is_account_confirmed': ''},
            {'username': factory.user_name(), 'is_account_confirmed': False},
        ],
        NewUserPasswordValidator('domain'),
        {
            0: NewUserPasswordValidator.error_message,
            5: NewUserPasswordValidator.error_message,
            6: NewUserPasswordValidator.error_message,
        }
    ),
    (
        [
            {'email': 'Joe Smith <email@example.com>'},
            {'email': 'email@example.com'}
        ],
        EmailValidator('domain', 'email'),
        {0: EmailValidator.error_message.format('email')}
    ),
    (
        [
            {'role': 'r3'},
            {'role': 'r2'},
            {},
        ],
        RoleValidator('domain', {'r1', 'r2'}),
        {0: RoleValidator.error_message.format('r3')}
    ),
    (
        [
            {'group': ['g1', 'g2']},
            {'group': ['g1', 'g3']},
            {},
        ],
        GroupValidator('domain', {'g1', 'g2'}),
        {1: GroupValidator.error_message.format('g3')}
    ),
    (
        [
            {'username': 'abc'},
            {'username': 123},
            {'username': 10.3},
            {},
        ],
        UsernameTypeValidator('domain'),
        {2: UsernameTypeValidator.error_message}
    ),
]


@pytest.mark.parametrize("specs, validator, errors", TEST_CASES)
def test_validators(specs, validator, errors):
    for i, spec in enumerate(specs):
        if i in errors:
            with assert_raises(UserUploadError, msg=errors[i]):
                validator(spec)
        else:
            validator(spec)


@nottest
def _test_duplicates(specs, duplicates, check=None):
    validator = DuplicateValidator('domain', 'name', specs, check_function=check)
    for spec in specs:
        yield validator, spec, duplicates


@pytest.mark.parametrize("validator, spec, duplicates", list(_test_duplicates(
    [
        {'name': 1},
        {'name': 2},
        {'name': 3},
        {'name': 2},
        {'name': 3},
        {},
    ],
    (2, 3),
)))
def test_duplicates(validator, spec, duplicates):
    if spec.get('name') in duplicates:
        with assert_raises(UserUploadError, msg=validator.error_message):
            validator(spec)
    else:
        validator(spec)


@pytest.mark.parametrize("validator, spec, duplicates", list(_test_duplicates(
    [
        {'name': 1},
        {'name': 2},
        {'name': 2},
        {'name': 3},
        {'name': 3},
        {},
    ],
    (3,),
    check=(lambda item: item != 2)
)))
def test_duplicates_with_check(validator, spec, duplicates):
    if spec.get('name') in duplicates:
        with assert_raises(UserUploadError, msg=validator.error_message):
            validator(spec)
    else:
        validator(spec)


def test_existing_users():
    user_specs = [
        {'username': 'hello'},
        {'username': 'bob'},
    ]

    with patch('corehq.apps.user_importer.validation.get_existing_usernames',
               return_value=['bob@domain.commcarehq.org']):
        validator = ExistingUserValidator('domain', user_specs)

    validator(user_specs[0])
    with assert_raises(UserUploadError):
        validator(user_specs[1])


def test_validating_sms_confirmation_entry():
    validator = ConfirmationSmsValidator("domain")
    # No entry for confirmation sms
    user_spec = {'username': 'hello'}
    validation_result = validator.validate_spec(user_spec)
    assert validation_result is None

    # Confirmation sms set to False
    user_spec = {ConfirmationSmsValidator.confirmation_sms_header: 'False'}
    validation_result = validator.validate_spec(user_spec)
    assert validation_result is None

    # Confirmation sms set to True, existing user, active
    user_spec = {
        ConfirmationSmsValidator.confirmation_sms_header: 'True',
        'user_id': 1,
        ConfirmationSmsValidator.active_status_header: 'True'
    }
    validation_result = validator.validate_spec(user_spec)
    assert validation_result == "When 'send_confirmation_sms' is True for an "\
        "existing user, is_active must be empty or set to False."

    # Confirmation sms set to True, existing user, account confirmed
    user_spec = {
        ConfirmationSmsValidator.confirmation_sms_header: 'True',
        'user_id': 1,
        ConfirmationSmsValidator.account_confirmed_header: 'True'
    }
    validation_result = validator.validate_spec(user_spec)
    assert validation_result == "When 'send_confirmation_sms' is True for an "\
        "existing user, is_account_confirmed must be empty."

    # Confirmation sms set to True, existing user, account confirmed, active
    user_spec = {
        ConfirmationSmsValidator.confirmation_sms_header: 'True',
        'user_id': 1,
        ConfirmationSmsValidator.account_confirmed_header: 'True',
        ConfirmationSmsValidator.active_status_header: 'True'
    }
    validation_result = validator.validate_spec(user_spec)
    expect = "When 'send_confirmation_sms' is True for an existing user, " \
        "is_active must be empty or set to False and is_account_confirmed must be empty."
    assert validation_result == expect

    # Confirmation sms set to True, existing user, account not confirmed, not active
    user_spec = {
        ConfirmationSmsValidator.confirmation_sms_header: 'True',
        'user_id': 1,
        ConfirmationSmsValidator.active_status_header: 'False'
    }
    validation_result = validator.validate_spec(user_spec)
    assert validation_result is None

    # Confirmation sms set to True, new user, account not confirmed, not active
    user_spec = {
        ConfirmationSmsValidator.confirmation_sms_header: 'True',
        ConfirmationSmsValidator.active_status_header: 'False'
    }
    validation_result = validator.validate_spec(user_spec)
    assert validation_result is None

    # Confirmation sms set to True, new user, active
    user_spec = {
        ConfirmationSmsValidator.confirmation_sms_header: 'True',
        ConfirmationSmsValidator.active_status_header: 'True'
    }
    validation_result = validator.validate_spec(user_spec)
    assert validation_result == "When 'send_confirmation_sms' is True for a new user, "\
        "is_active must be either empty or set to False."

    # Confirmation sms set to True, new user, active, account confirmed
    user_spec = {
        ConfirmationSmsValidator.confirmation_sms_header: 'True',
        ConfirmationSmsValidator.active_status_header: 'True',
        ConfirmationSmsValidator.account_confirmed_header: 'True'
    }
    validation_result = validator.validate_spec(user_spec)
    assert validation_result == "When 'send_confirmation_sms' is True for a new user, "\
        "is_active and is_account_confirmed must be either empty or set to False."


class TestLocationValidator(LocationHierarchyTestCase):

    domain = 'test-domain'
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
        ])
    ]

    @classmethod
    def setUpClass(cls):
        delete_all_users()
        super(TestLocationValidator, cls).setUpClass()
        cls.upload_user = WebUser.create(cls.domain, 'username', 'password', None, None)
        cls.upload_user.set_location(cls.domain, cls.locations['Middlesex'])
        restrict_user_by_location(cls.domain, cls.upload_user)
        cls.editable_user = WebUser.create(cls.domain, 'editable-user', 'password', None, None)
        cls.validator = LocationValidator(cls.domain, cls.upload_user,
                                          SiteCodeToLocationCache(cls.domain), True)

    def test_success(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result is None

    def test_cant_edit_web_user(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Suffolk'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_user_access

        user_spec = {'username': self.editable_user.username}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_user_access

    def test_cant_edit_commcare_user(self):
        self.cc_user_validator = LocationValidator(self.domain, self.upload_user,
                                                SiteCodeToLocationCache(self.domain), False)
        self.editable_cc_user = CommCareUser.create(self.domain, 'cc-username', 'password', None, None)
        self.editable_cc_user.reset_locations([self.locations['Suffolk'].location_id])
        user_spec = {'user_id': self.editable_cc_user._id,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.cc_user_validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_user_access

        user_spec = {'user_id': self.editable_cc_user._id}
        validation_result = self.cc_user_validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_user_access

    def test_cant_edit_invitation(self):
        self.invitation = Invitation.objects.create(
            domain=self.domain,
            email='invite-user@dimagi.com',
            invited_by='a@dimagi.com',
            invited_on=datetime.utcnow()
        )
        self.invitation.assigned_locations.set([self.locations['Suffolk']])
        user_spec = {'username': self.invitation.email,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_user_access

        user_spec = {'username': self.invitation.email}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_user_access

    def test_cant_add_location(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Suffolk'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_location_access.format(
            self.locations['Suffolk'].site_code)

    def test_cant_remove_location(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Suffolk'].location_id,
                                                         self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_location_access.format(
            self.locations['Suffolk'].site_code)

    def test_cant_remove_all_locations(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Suffolk'].location_id,
                                                         self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': []}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == self.validator.error_message_location_access.format(
            self.locations['Suffolk'].site_code)

    @flag_enabled('USH_RESTORE_FILE_LOCATION_CASE_SYNC_RESTRICTION')
    def test_location_not_has_users(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Middlesex'].location_id])
        self.locations['Cambridge'].location_type.has_users = False
        self.locations['Cambridge'].location_type.save()
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Cambridge'].site_code,
                                       self.locations['Middlesex'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        error_message_location_not_has_users = (
            "These locations cannot have users assigned because of their "
            "organization level settings: {}."
        )
        assert validation_result == error_message_location_not_has_users.format(
            self.locations['Cambridge'].site_code)

    @classmethod
    def tearDownClass(cls):
        super(LocationHierarchyTestCase, cls).tearDownClass()
        delete_all_users()


@flag_enabled('RESTRICT_USER_PROFILE_ASSIGNMENT')
class TestProfileValidator(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        delete_all_users()
        super(TestProfileValidator, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.upload_user = WebUser.create(cls.domain, 'username', 'password', None, None)
        cls.editable_user = WebUser.create(cls.domain, 'editable-user', 'password', None, None)
        cls.editable_user2 = WebUser.create(cls.domain, 'editable-user2', 'password', None, None)
        cls.definition = CustomDataFieldsDefinition(domain=cls.domain, field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.profile1 = CustomDataFieldsProfile(
            name='p1',
            fields={},
            definition=cls.definition,
        )
        cls.profile1.save()
        cls.profile2 = CustomDataFieldsProfile(
            name='p2',
            fields={},
            definition=cls.definition,
        )
        cls.profile2.save()
        all_user_profiles_by_name = {'p1': cls.profile1, 'p2': cls.profile2}
        cls.editable_user.get_user_data(cls.domain).profile_id = cls.profile1.id
        cls.editable_user.save()
        cls.web_user_import_validator = ProfileValidator(cls.domain, cls.upload_user,
                                                True, all_user_profiles_by_name)
        cls.invitation = Invitation.objects.create(
            domain=cls.domain,
            email='invite-user@dimagi.com',
            invited_by='a@dimagi.com',
            invited_on=datetime.utcnow(),
            profile=cls.profile1
        )
        cls.invitation2 = Invitation.objects.create(
            domain=cls.domain,
            email='invite-user2@dimagi.com',
            invited_by='a@dimagi.com',
            invited_on=datetime.utcnow(),
            profile=None
        )
        cls.edit_all_profiles_role = UserRole.create(
            domain=cls.domain_obj.name,
            name='Edit All Profiles',
            permissions=HqPermissions(edit_user_profile=True)
        )
        cls.edit_p1_profiles_role = UserRole.create(
            domain=cls.domain_obj.name,
            name='Edit Profile p1',
            permissions=HqPermissions(edit_user_profile=False, edit_user_profile_list=[str(cls.profile1.id)])
        )
        cls.edit_p2_profiles_role = UserRole.create(
            domain=cls.domain_obj.name,
            name='Edit Profile p1',
            permissions=HqPermissions(edit_user_profile=False, edit_user_profile_list=[str(cls.profile2.id)])
        )
        cls.edit_p1_and_p2_profiles_role = UserRole.create(
            domain=cls.domain_obj.name,
            name='Edit Profile p1 and p2',
            permissions=HqPermissions(edit_user_profile=False, edit_user_profile_list=[str(cls.profile1.id),
                                                                                       str(cls.profile2.id)])
        )

    def test_edit_all_profiles_no_issues(self):
        self.upload_user.set_role(self.domain, self.edit_all_profiles_role.get_qualified_id())
        for username in [self.editable_user.username, self.invitation.email]:
            user_spec = {'username': username, 'user_profile': 'p2'}
            validation_result = self.web_user_import_validator.validate_spec(user_spec)
            assert validation_result is None
        for username in [self.editable_user2.username, self.invitation2.email]:
            user_spec = {'username': username, 'user_profile': 'p2'}
            validation_result = self.web_user_import_validator.validate_spec(user_spec)
            assert validation_result is None

    def test_change_profile_no_issue(self):
        self.upload_user.set_role(self.domain, self.edit_p1_and_p2_profiles_role.get_qualified_id())
        for username in [self.editable_user.username, self.invitation.email]:
            user_spec = {'username': username, 'user_profile': 'p2'}
            validation_result = self.web_user_import_validator.validate_spec(user_spec)
            assert validation_result is None

    def test_invalid_profile_name(self):
        self.upload_user.set_role(self.domain, self.edit_all_profiles_role.get_qualified_id())
        for username in [self.editable_user2.username, self.invitation2.email]:
            user_spec = {'username': username, 'user_profile': 'r1'}
            validation_result = self.web_user_import_validator.validate_spec(user_spec)
        assert validation_result == ProfileValidator.error_message_nonexisting_profile.format('r1')

    def test_cant_assign_profile_without_the_permission(self):
        self.upload_user.set_role(self.domain, self.edit_p1_profiles_role.get_qualified_id())
        for username in [self.editable_user.username, self.invitation.email]:
            user_spec = {'username': username, 'user_profile': 'p2'}
            validation_result = self.web_user_import_validator.validate_spec(user_spec)
            assert validation_result == ProfileValidator.error_message_new_user_profile_access.format('p2')

    def test_removing_and_assigning_profile(self):
        self.upload_user.set_role(self.domain, self.edit_p1_profiles_role.get_qualified_id())
        user_spec = {'username': self.editable_user.username, 'user_profile': ''}
        validation_result = self.web_user_import_validator.validate_spec(user_spec)
        assert validation_result is None
        user_spec = {'username': self.editable_user2.username, 'user_profile': 'p1'}
        validation_result = self.web_user_import_validator.validate_spec(user_spec)
        assert validation_result is None

    def test_no_error_when_unaccessible_profile_didnt_change(self):
        self.upload_user.set_role(self.domain, self.edit_p2_profiles_role.get_qualified_id())
        user_spec = {'username': self.editable_user.username, 'user_profile': 'p1'}
        validation_result = self.web_user_import_validator.validate_spec(user_spec)
        assert validation_result is None

    def test_cant_edit_profile_no_access(self):
        self.upload_user.set_role(self.domain, self.edit_p2_profiles_role.get_qualified_id())
        user_spec = {'username': self.editable_user.username, 'user_profile': 'p2'}
        validation_result = self.web_user_import_validator.validate_spec(user_spec)
        assert validation_result == ProfileValidator.error_message_original_user_profile_access

    def test_validation_error_when_profile_required(self):
        self.definition.profile_required_for_user_type = [UserFieldsView.WEB_USER, UserFieldsView.COMMCARE_USER]
        self.definition.save()
        self.upload_user.set_role(self.domain, self.edit_p2_profiles_role.get_qualified_id())
        user_spec = {'username': self.editable_user.username}
        validation_result = self.web_user_import_validator.validate_spec(user_spec)
        expected_result = ProfileValidator.error_message_profile_must_be_assigned.format(
            "Web Users, Mobile Workers"
        )
        assert validation_result == expected_result

    def test_no_validation_error_when_profile_required_and_supplied(self):
        self.definition.profile_required_for_user_type = [UserFieldsView.WEB_USER, UserFieldsView.COMMCARE_USER]
        self.definition.save()
        self.upload_user.set_role(self.domain, self.edit_p2_profiles_role.get_qualified_id())
        user_spec = {'username': self.editable_user.username, 'user_profile': 'p1'}
        validation_result = self.web_user_import_validator.validate_spec(user_spec)
        assert validation_result is None

    @classmethod
    def tearDownClass(cls):
        super(TestProfileValidator, cls).tearDownClass()
        delete_all_users()


class TestCustomDataValidator(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        delete_all_users()
        super(TestCustomDataValidator, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        cls.definition = CustomDataFieldsDefinition(
            domain=cls.domain,
            field_type=UserFieldsView.field_type
        )
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='corners',
                is_required=False,
                label='Number of corners',
                regex='^[0-9]+$',
                regex_msg='This should be a number',
            ),
            Field(
                slug='prefix',
                is_required=False,
                label='Prefix',
                choices=['tri', 'tetra', 'penta'],
            ),
            Field(
                slug='color',
                is_required=True,
                required_for=[CommcareUserFieldsView.user_type],
                label='Color',
            ),
            Field(
                slug='shape_type',
                is_required=True,
                required_for=[WebUserFieldsView.user_type],
                label='Type of Shape',
            )
        ])
        cls.profile1 = CustomDataFieldsProfile(
            name='p1',
            fields={'corners': '3', 'color': 'blue', 'shape_type': 'triangle'},
            definition=cls.definition,
        )
        cls.profile1.save()

    def test_valid_fields_without_profile(self):
        import_validator = CustomDataValidator(self.domain, None, True)
        custom_data_spec = {
            'data': {'corners': '3', 'color': 'blue', 'shape_type': 'triangle'},
        }
        validation_result = import_validator.validate_spec(custom_data_spec)
        assert validation_result == ''

    def test_invalid_fields_with_valid_profile(self):
        user_profiles_by_name = {'p1': self.profile1}
        import_validator = CustomDataValidator(self.domain, user_profiles_by_name, True)
        custom_data_spec = {
            'data': {'corners': 'three'},
            'user_profile': 'p1',
        }
        validation_result = import_validator.validate_spec(custom_data_spec)
        assert validation_result == ''

    def test_invalid_web_user_required_field(self):
        import_validator = CustomDataValidator(self.domain, None, True)
        custom_data_spec = {
            'data': {'color': 'blue'},
        }
        validation_result = import_validator.validate_spec(custom_data_spec)
        assert validation_result == "Type of Shape is required."

    def test_invalid_commcare_user_required_field(self):
        import_validator = CustomDataValidator(self.domain, None, False)
        custom_data_spec = {
            'data': {'shape_type': 'triangle'},
        }
        validation_result = import_validator.validate_spec(custom_data_spec)
        assert validation_result == "Color is required."

    def test_invalid_choices_field(self):
        import_validator = CustomDataValidator(self.domain, None, True)
        custom_data_spec = {
            'data': {'prefix': 'bi', 'color': 'blue', 'shape_type': 'triangle'},
        }
        validation_result = import_validator.validate_spec(custom_data_spec)
        assert validation_result == (
            "'bi' is not a valid choice for Prefix. "
            "The available options are: tri, tetra, penta."
        )

    def test_invalild_regex_fields(self):
        import_validator = CustomDataValidator(self.domain, None, True)
        custom_data_spec = {
            'data': {'corners': 'three', 'color': 'blue', 'shape_type': 'triangle'},
        }
        validation_result = import_validator.validate_spec(custom_data_spec)
        assert validation_result == (
            "'three' is not a valid match for Number of corners"
        )


class TestUtil(TestCase):
    domain = "test-domain"

    def test_get_invitation_or_editable_user(self):
        create_domain(self.domain)
        editable_user = WebUser.create(self.domain, 'editable-user', 'password', None, None)
        invitation = Invitation.objects.create(
            domain=self.domain,
            email='invite-user@dimagi.com',
            invited_by='a@dimagi.com',
            invited_on=datetime.utcnow(),
        )
        spec = {'username': editable_user.username}
        self.assertEqual(editable_user.userID,
                         _get_invitation_or_editable_user(spec, True, self.domain).editable_user.userID)
        self.assertEqual(editable_user.userID,
                         _get_invitation_or_editable_user(spec, False, self.domain).editable_user.userID)
        spec = {'user_id': editable_user.userID}
        self.assertEqual(editable_user.userID,
                         _get_invitation_or_editable_user(spec, False, self.domain).editable_user.userID)

        spec = {'username': invitation.email}
        self.assertEqual(invitation, _get_invitation_or_editable_user(spec, True, self.domain).invitation)

        spec = {}
        self.assertEqual(None, _get_invitation_or_editable_user(spec, True, self.domain).editable_user)
        self.assertEqual(None, _get_invitation_or_editable_user(spec, False, self.domain).editable_user)


class TestTableauRoleValidator(TestCase):
    domain = 'test-domain'

    def test_valid_role(self):
        validator = TableauRoleValidator(self.domain)
        spec = {'tableau_role': TableauUser.Roles.EXPLORER.value}
        self.assertIsNone(validator.validate_spec(spec))

    def test_invalid_role(self):
        validator = TableauRoleValidator(self.domain)
        spec = {'tableau_role': 'invalid_role'}
        expected_error = TableauRoleValidator._error_message.format(
            'invalid_role', ', '.join([e.value for e in TableauUser.Roles])
        )
        self.assertEqual(validator.validate_spec(spec), expected_error)

    def test_no_role(self):
        validator = TableauRoleValidator(self.domain)
        spec = {}
        self.assertIsNone(validator.validate_spec(spec))


class TestTableauGroupsValidator(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.allowed_groups = ['group1', 'group2']
        cls.tableau_server = TableauServer.objects.create(
            domain=cls.domain,
            allowed_tableau_groups=cls.allowed_groups
        )
        cls.all_specs = [{'tableau_groups': 'group1,group2'}]

    def test_valid_groups(self):
        validator = TableauGroupsValidator(self.domain, self.all_specs)
        spec = {'tableau_groups': 'group1,group2'}
        self.assertIsNone(validator.validate_spec(spec))

    def test_invalid_groups(self):
        validator = TableauGroupsValidator(self.domain, self.all_specs)
        spec = {'tableau_groups': 'group1,invalid_group'}
        expected_error = TableauGroupsValidator._error_message.format(
            'invalid_group', ', '.join(self.allowed_groups)
        )
        self.assertEqual(validator.validate_spec(spec), expected_error)

    def test_no_groups(self):
        validator = TableauGroupsValidator(self.domain, self.all_specs)
        spec = {}
        self.assertIsNone(validator.validate_spec(spec))

    def test_empty_groups(self):
        validator = TableauGroupsValidator(self.domain, self.all_specs)
        spec = {'tableau_groups': ''}
        self.assertIsNone(validator.validate_spec(spec))
