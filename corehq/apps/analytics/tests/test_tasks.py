from django.test import SimpleTestCase
from ..tasks import _email_is_valid


class TestEmailValidation(SimpleTestCase):
    def test_mozej_dot_com_is_invalid(self):
        self.assertFalse(_email_is_valid('test@mozej.com'))

    def test_mailna_dot_me_is_invalid(self):
        self.assertFalse(_email_is_valid('test@mailna.me'))

    def test_generic_email_is_valid(self):
        self.assertTrue(_email_is_valid('test@google.com'))

    def test_malformed_email_is_not_valid(self):
        self.assertFalse(_email_is_valid('bob'))
