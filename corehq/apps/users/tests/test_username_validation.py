from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.exceptions import (
    InvalidDomainException,
    InvalidUsernameException,
    UsernameAlreadyExists,
)
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.validation import (
    ReservedUsernameException,
    _check_for_reserved_usernames,
    _ensure_username_is_available,
    _ensure_valid_username,
    validate_mobile_username,
)


class TestMobileUsernameValidation(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain('test-domain')
        cls.addClassCleanup(cls.domain_obj.delete)

    def setUp(self) -> None:
        super().setUp()
        self.user = CommCareUser.create(self.domain, 'test-user@test-domain.commcarehq.org', 'abc123', None, None)
        self.addCleanup(self.user.delete, self.domain, None)

    def test_valid_username_returns_successfully(self):
        username = validate_mobile_username('test-user-1', self.domain)
        self.assertEqual(username, 'test-user-1@test-domain.commcarehq.org')

    def test_none_username_raises_exception(self):
        with self.assertRaises(InvalidUsernameException):
            validate_mobile_username(None, self.domain)

    def test_none_domain_raises_exception(self):
        with self.assertRaises(InvalidDomainException):
            validate_mobile_username('test-user-1', None)

    def test_reserved_username_raises_exception(self):
        with self.assertRaises(ReservedUsernameException):
            validate_mobile_username('admin', self.domain)

    def test_empty_username_raises_exception(self):
        with self.assertRaises(InvalidUsernameException):
            validate_mobile_username('', self.domain)

    def test_invalid_email_raises_exception(self):
        with self.assertRaises(InvalidUsernameException):
            validate_mobile_username('test..user', self.domain)

    def test_already_used_username_raises_exception(self):
        with self.assertRaises(UsernameAlreadyExists):
            validate_mobile_username('test-user', self.domain)


class TestCheckForReservedUsernames(SimpleTestCase):

    def test_non_reserved_username_does_not_raise_exception(self):
        try:
            _check_for_reserved_usernames('not-reserved')
        except ReservedUsernameException:
            self.fail(f'Unexpected raised exception: {ReservedUsernameException}')

    def test_admin_raises_exception(self):
        with self.assertRaises(ReservedUsernameException):
            _check_for_reserved_usernames('admin')

    def test_demo_user_raises_exception(self):
        with self.assertRaises(ReservedUsernameException):
            _check_for_reserved_usernames('demo_user')


class TestEnsureValidUsername(SimpleTestCase):

    def test_valid_email_does_not_raise_exception(self):
        try:
            _ensure_valid_username('username@domain.commcarehq.org')
        except InvalidUsernameException:
            self.fail(f'Unexpected raised exception: {InvalidUsernameException}')

    def test_invalid_raises_exception(self):
        with self.assertRaises(InvalidUsernameException):
            _ensure_valid_username('username%domain.commcarehq.org')

    def test_trailing_period_raises_exception(self):
        with self.assertRaises(InvalidUsernameException):
            _ensure_valid_username('username.@domain.commcarehq.org')

    def test_double_period_raises_exception(self):
        with self.assertRaises(InvalidUsernameException):
            _ensure_valid_username('user..name@domain.commcarehq.org')


class TestEnsureUsernameIsAvailable(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain('test-domain')
        cls.addClassCleanup(cls.domain_obj.delete)

    def setUp(self) -> None:
        super().setUp()
        self.user = CommCareUser.create(self.domain, 'test-user@test-domain.commcarehq.org', 'abc123', None, None)
        self.addCleanup(self.user.delete, self.domain, None)

    def test_username_is_available(self):
        try:
            _ensure_username_is_available('unused-test-user@test-domain.commcarehq.org')
        except UsernameAlreadyExists:
            self.fail(f'Unexpected raised exception: {InvalidUsernameException}')

    def test_username_is_actively_in_use(self):
        try:
            _ensure_username_is_available('test-user@test-domain.commcarehq.org')
        except UsernameAlreadyExists as e:
            self.assertFalse(e.is_deleted)
        else:
            self.fail(f'Expected raised exception: {UsernameAlreadyExists}')

    def test_username_was_previously_used(self):
        self.user.retire(self.domain, None)
        try:
            _ensure_username_is_available('test-user@test-domain.commcarehq.org')
        except UsernameAlreadyExists as e:
            self.assertTrue(e.is_deleted)
        else:
            self.fail(f'Expected raised exception: {UsernameAlreadyExists}')
