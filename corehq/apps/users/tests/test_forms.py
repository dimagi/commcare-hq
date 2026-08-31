import string

from django.conf import settings
from django.test import SimpleTestCase

from corehq.apps.domain.forms import clean_password

from ..forms import STRONG_PASSWORD_LEN, generate_strong_password


class TestGenerateStrongPassword(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.password = generate_strong_password()

    def test_length(self):
        self.assertEqual(len(self.password), STRONG_PASSWORD_LEN)

    def test_contains_lower(self):
        self.assertTrue(any(c.islower() for c in self.password))

    def test_contains_upper(self):
        self.assertTrue(any(c.isupper() for c in self.password))

    def test_contains_digit(self):
        self.assertTrue(any(c.isdigit() for c in self.password))

    def test_contains_punc(self):
        self.assertTrue(any(c in string.punctuation for c in self.password))

    def test_length_is_not_below_configured_minimum(self):
        # Generated passwords are offered to users as-is, so a generator
        # shorter than the minimum would suggest a password that then fails
        # validation on submit.
        assert STRONG_PASSWORD_LEN >= settings.MINIMUM_PASSWORD_LENGTH

    def test_passes_password_validation(self):
        assert clean_password(self.password) == self.password
