from faker import Faker
from mock import patch
from testil import assert_raises

from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.validation import (
    DuplicateValidator,
    EmailValidator,
    ExistingUserValidator,
    GroupValidator,
    IsActiveValidator,
    UsernameLengthValidator,
    NewUserPasswordValidator,
    RoleValidator,
    UsernameTypeValidator,
    RequiredFieldsValidator,
    UsernameValidator,
)

factory = Faker()
factory.seed(1571040848)

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
        IsActiveValidator('domain'),
        {2: IsActiveValidator.error_message}
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
            {'username': factory.user_name(), 'password': 123}
        ],
        NewUserPasswordValidator('domain'),
        {0: NewUserPasswordValidator.error_message}
    ),
    (
        [
            {'email': 'Joe Smith <email@example.com>'},
            {'email': 'email@example.com'}
        ],
        EmailValidator('domain'),
        {0: EmailValidator.error_message}
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
