from faker import Faker
from testil import assert_raises

from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.validation import (
    Duplicates,
    EmailValidator,
    GroupValidator,
    IsActive,
    LongUsernames,
    NewUserPassword,
    RoleValidator,
    UsernameOrUserIdRequired,
    UsernameValidator,
)

factory = Faker()
factory.seed(1571040848)

# tuple(specs, validator class, errors dict(row_index: message)
TEST_CASES = [
    (
        [
            {'username': 'jack black <email'},
            {'username': factory.user_name()}
        ],
        UsernameValidator('domain'),
        {0: UsernameValidator.error_message}
    ),
    (
        [
            {'is_active': 'true'},
            {'is_active': 'false'},
            {'is_active': 'active'}
        ],
        IsActive('domain'),
        {2: IsActive.error_message}
    ),
    (
        [
            {'username': factory.user_name()},
            {'user_id': factory.uuid4()},
            {}
        ],
        UsernameOrUserIdRequired('domain'),
        {2: UsernameOrUserIdRequired.error_message}
    ),
    (
        [
            {'username': 'verylongusernamelessthan30char'},
            {'username': 'verylongusernamemorethan30chars'}
        ],
        LongUsernames('domain', 30),
        {1: LongUsernames._error_message.format(length=30)}
    ),
    (
        [
            {'username': factory.user_name()},
            {'username': factory.user_name(), 'user_id': factory.uuid4()},
            {'username': factory.user_name(), 'password': factory.password()}
        ],
        NewUserPassword('domain'),
        {0: NewUserPassword.error_message}
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
    validator = Duplicates('domain', 'name', specs, check_function=check)

    def _test(spec):
        if spec.get('name') in duplicates:
            with assert_raises(UserUploadError, msg=validator.error_message):
                validator(spec)
        else:
            validator(spec)

    for spec in specs:
        yield _test, spec
