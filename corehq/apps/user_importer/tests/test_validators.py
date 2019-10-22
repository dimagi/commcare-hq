from faker import Faker
from testil import assert_raises

from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.validation import UsernameValidator, IsActive, UsernameOrUserIdRequired

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
