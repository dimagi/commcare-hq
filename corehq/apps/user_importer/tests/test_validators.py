from datetime import datetime
from django.test import TestCase
from faker import Faker
from unittest.mock import patch
from testil import assert_raises

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import LocationHierarchyTestCase, restrict_user_by_location
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
    LocationAccessValidator,
    _get_invitation_or_editable_user,
)
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, HqPermissions, Invitation, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.util.test_utils import flag_enabled
from corehq.apps.custom_data_fields.models import (CustomDataFieldsDefinition,
    CustomDataFieldsProfile)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView

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


def test_validators():
    def _test_spec(validator, specs, errors):
        for i, spec in enumerate(specs):
            if i in errors:
                with assert_raises(UserUploadError, msg=errors[i]):
                    validator(spec)
            else:
                validator(spec)

    for specs, validator, errors in TEST_CASES:
        yield _test_spec, validator, specs, errors


def test_duplicates():
    specs = [
        {'name': 1},
        {'name': 2},
        {'name': 3},
        {'name': 2},
        {'name': 3},
        {},
    ]
    duplicates = (2, 3)
    yield from _test_duplicates(specs, duplicates)


def test_duplicates_with_check():
    specs = [
        {'name': 1},
        {'name': 2},
        {'name': 2},
        {'name': 3},
        {'name': 3},
        {},
    ]
    duplicates = (3,)

    def check(item):
        return item != 2

    yield from _test_duplicates(specs, duplicates, check)


def _test_duplicates(specs, duplicates, check=None):
    validator = DuplicateValidator('domain', 'name', specs, check_function=check)

    def _test(spec):
        if spec.get('name') in duplicates:
            with assert_raises(UserUploadError, msg=validator.error_message):
                validator(spec)
        else:
            validator(spec)

    for spec in specs:
        yield _test, spec


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


class TestLocationAccessValidator(LocationHierarchyTestCase):

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
        super(TestLocationAccessValidator, cls).setUpClass()
        cls.upload_user = WebUser.create(cls.domain, 'username', 'password', None, None)
        cls.upload_user.set_location(cls.domain, cls.locations['Middlesex'])
        restrict_user_by_location(cls.domain, cls.upload_user)
        cls.editable_user = WebUser.create(cls.domain, 'editable-user', 'password', None, None)
        cls.validator = LocationAccessValidator(cls.domain, cls.upload_user,
                                                SiteCodeToLocationCache(cls.domain), True)

    def testSuccess(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result is None

    def testCantEditWebUser(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Suffolk'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == ("Based on your locations do not have permission to edit this user or user "
                                     "invitation")

    def testCantEditCommCareUser(self):
        self.cc_user_validator = LocationAccessValidator(self.domain, self.upload_user,
                                                SiteCodeToLocationCache(self.domain), False)
        self.editable_cc_user = CommCareUser.create(self.domain, 'cc-username', 'password', None, None)
        self.editable_cc_user.reset_locations([self.locations['Suffolk'].location_id])
        user_spec = {'user_id': self.editable_cc_user._id,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.cc_user_validator.validate_spec(user_spec)
        assert validation_result == ("Based on your locations do not have permission to edit this user or user "
                                     "invitation")

    def testCantEditInvitation(self):
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
        assert validation_result == ("Based on your locations do not have permission to edit this user or user "
                                     "invitation")

    def testCantAddLocation(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Suffolk'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == ("You do not have permission to assign or remove these locations: "
                                     "suffolk")

    def testCantRemoveLocation(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Suffolk'].location_id,
                                                         self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        assert validation_result == ("You do not have permission to assign or remove these locations: "
                                     "suffolk")

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

    @classmethod
    def tearDownClass(cls):
        super(TestProfileValidator, cls).tearDownClass()
        delete_all_users()


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
