from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from corehq.apps.settings.validators import validate_international_phonenumber


class ValidateInternationalPhonenumberTests(SimpleTestCase):

    def test_empty_string_raises_error(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('')

    def test_valid_us_number_does_not_raise_error(self):
        validate_international_phonenumber('+16175555555')

    def test_invalid_us_number_raises_error(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('+1617555555')

    def test_valid_south_africa_number_does_not_raise_error(self):
        validate_international_phonenumber('+27623555555')

    def test_invalid_south_africa_number_raises_error(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('+27555555555')

    def test_valid_india_number_does_not_raise_error(self):
        validate_international_phonenumber('+911125555555')

    def test_invalid_india_number_raises_error(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('+915555555555')

    def test_invalid_international_number_raises_error(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('6175555555')
