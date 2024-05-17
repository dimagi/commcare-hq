from datetime import datetime
from faker import Faker
from unittest.mock import patch
from testil import assert_raises

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
    LocationAccessValidator)
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser, Invitation

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
            {'user_profile': 'p1'},
            {'user_profile': 'r1'},
            {},
        ],
        ProfileValidator('domain', {'p1', 'p2'}),
        {1: ProfileValidator.error_message.format('r1')}
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
        # cls.upload_user.reset_locations(cls.domain, [cls.locations['Middlesex'].location_id])
        cls.validator = LocationAccessValidator(cls.domain, cls.upload_user,
                                                SiteCodeToLocationCache(cls.domain), True)

    def testSuccess(self):
        self.editable_user.reset_locations(self.domain, [self.locations['Cambridge'].location_id])
        user_spec = {'username': self.editable_user.username,
                     'location_code': [self.locations['Middlesex'].site_code,
                                       self.locations['Cambridge'].site_code]}
        validation_result = self.validator.validate_spec(user_spec)
        print(validation_result)
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
