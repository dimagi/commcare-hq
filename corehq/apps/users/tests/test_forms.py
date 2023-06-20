import string

from django.test import SimpleTestCase

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
