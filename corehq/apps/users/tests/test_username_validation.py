from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.validation import (
    _validate_complete_username,
    validate_mobile_username,
)


class TestMobileUsernameValidation(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain('test-domain')
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.user = CommCareUser.create(cls.domain, 'test-user@test-domain.commcarehq.org', 'abc123', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain, None)

    def test_valid_username_returns_successfully(self):
        username = validate_mobile_username('test-user-1@test-domain.commcarehq.org', self.domain)
        self.assertEqual(username, 'test-user-1@test-domain.commcarehq.org')

    def test_none_username_raises_exception(self):
        with self.assertRaises(ValidationError):
            validate_mobile_username(None, self.domain)

    def test_empty_username_raises_exception(self):
        with self.assertRaises(ValidationError):
            validate_mobile_username('', self.domain)

    def test_reserved_username_raises_exception(self):
        with self.assertRaises(ValidationError):
            validate_mobile_username('admin@test-domain.commcarehq.org', self.domain)

    def test_invalid_email_raises_exception(self):
        with self.assertRaises(ValidationError):
            validate_mobile_username('test..user@test-domain.commcarehq.org', self.domain)

    def test_already_used_username_raises_exception(self):
        with self.assertRaises(ValidationError):
            validate_mobile_username('test-user@test-domain.commcarehq.org', self.domain)


class TestValidateCompleteUsername(SimpleTestCase):

    def test_valid_email_does_not_raise_exception(self):
        try:
            _validate_complete_username('username@domain.commcarehq.org', 'domain')
        except ValidationError:
            self.fail(f'Unexpected raised exception: {ValidationError}')

    def test_invalid_raises_exception(self):
        with self.assertRaises(ValidationError):
            _validate_complete_username('username%domain.commcarehq.org', 'domain')

    def test_trailing_period_raises_exception(self):
        with self.assertRaises(ValidationError):
            _validate_complete_username('username.@domain.commcarehq.org', 'domain')

    def test_double_period_raises_exception(self):
        with self.assertRaises(ValidationError):
            _validate_complete_username('user..name@domain.commcarehq.org', 'domain')

    def test_incorrect_email_domain_raises_exception(self):
        with self.assertRaises(ValidationError):
            _validate_complete_username('user@domain2.commcarehq.org', 'domain')
