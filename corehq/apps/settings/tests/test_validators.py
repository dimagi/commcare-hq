from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from corehq.apps.settings.validators import validate_international_phonenumber


class GetTempFileTests(SimpleTestCase):

    def test_valid_us_number(self):
        validate_international_phonenumber('+16175555555')

    def test_invalid_international_number(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('6175555555')

    def test_valid_south_africa_number(self):
        validate_international_phonenumber('+27623555555')

    def test_invalid_south_africa_number(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('+27555555555')

    def test_valid_india_number(self):
        validate_international_phonenumber('+911125555555')

    def test_invalid_india_number(self):
        with self.assertRaises(ValidationError):
            validate_international_phonenumber('+915555555555')
