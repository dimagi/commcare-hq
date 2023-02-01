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

    def test_no_exception_rasied_if_valid_username(self):
        validate_mobile_username('test-user-1@test-domain.commcarehq.org', self.domain)

    def test_exception_raised_if_username_is_none(self):
        with self.assertRaises(ValidationError) as cm:
            validate_mobile_username(None, self.domain)

        self.assertEqual(cm.exception.message, "Username is required.")

    def test_exception_raised_if_username_is_empty(self):
        with self.assertRaises(ValidationError) as cm:
            validate_mobile_username('', self.domain)

        self.assertEqual(cm.exception.message, "Username is required.")

    def test_exception_raised_if_invalid_username(self):
        """See TestValidateCompleteUsername for more detailed tests"""
        with self.assertRaises(ValidationError):
            validate_mobile_username('invalid&test@test-domain.commcarehq.org', self.domain)

    def test_exception_raised_if_username_is_reserved(self):
        with self.assertRaises(ValidationError) as cm:
            validate_mobile_username('admin@test-domain.commcarehq.org', self.domain)

        self.assertEqual(cm.exception.message,
                         "Username 'admin@test-domain.commcarehq.org' is already taken or reserved.")

    def test_exception_raised_if_username_is_actively_in_use(self):
        with self.assertRaises(ValidationError) as cm:
            validate_mobile_username('test-user@test-domain.commcarehq.org', self.domain)

        self.assertEqual(cm.exception.message,
                         "Username 'test-user@test-domain.commcarehq.org' is already taken or reserved.")

    def test_exception_raised_if_username_was_previously_used(self):
        retired_user = CommCareUser.create(self.domain, 'retired@test-domain.commcarehq.org', 'abc123', None, None)
        self.addCleanup(retired_user.delete, self.domain, None)
        retired_user.retire(self.domain, None)

        with self.assertRaises(ValidationError) as cm:
            validate_mobile_username('retired@test-domain.commcarehq.org', self.domain)

        self.assertEqual(cm.exception.message,
                         "Username 'retired@test-domain.commcarehq.org' is already taken or reserved.")


class TestValidateCompleteUsername(SimpleTestCase):

    def test_no_exception_raised_if_valid_email(self):
        try:
            _validate_complete_username('username@domain.commcarehq.org', 'domain')
        except ValidationError:
            self.fail(f'Unexpected raised exception: {ValidationError}')

    def test_exception_raised_if_invalid_email(self):
        with self.assertRaises(ValidationError) as cm:
            _validate_complete_username('username%domain.commcarehq.org', 'domain')

        self.assertEqual(cm.exception.message,
                         "Username 'username%domain.commcarehq.org' must be a valid email address.")

    def test_exception_raised_if_invalid_username(self):
        """Invalid username refers to the first component of the email being invalid for HQ standards"""
        with self.assertRaises(ValidationError) as cm:
            _validate_complete_username('test%user@domain.commcarehq.org', 'domain')

        self.assertEqual(cm.exception.message,
                         "The username component 'test%user' of 'test%user@domain.commcarehq.org' may not "
                         "contain special characters.")

    def test_exception_raised_if_incorrect_email_domain(self):
        with self.assertRaises(ValidationError) as cm:
            _validate_complete_username('user@domain2.commcarehq.org', 'domain')

        self.assertEqual(cm.exception.message,
                         "The username email domain '@domain2.commcarehq.org' should be '@domain.commcarehq.org'.")
