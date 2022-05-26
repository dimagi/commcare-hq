from django.test import SimpleTestCase

from corehq.apps.sms.phonenumbers_helper import (
    PhoneNumberParseException,
    country_code_for_region,
    country_name_for_country_code,
    get_country_code_and_national_number,
    parse_phone_number,
)


class TestPhoneNumbersHelper(SimpleTestCase):

    def test_parse_country_coded_number_returns_correctly(self):
        number = parse_phone_number('+11234567890')
        self.assertEqual(number.country_code, 1)
        self.assertEqual(number.national_number, 1234567890)

    def test_parse_ignores_region_if_country_coded(self):
        number = parse_phone_number('+27123456789', region='US')
        self.assertEqual(number.country_code, 27)
        self.assertEqual(number.national_number, 123456789)

    def test_parse_without_country_coded_number_and_no_region_raises_exception(self):
        with self.assertRaises(PhoneNumberParseException):
            parse_phone_number('1234567890')

    def test_parse_without_country_coded_number_and_with_region_succeeds(self):
        number = parse_phone_number('1234567890', region='US')
        self.assertEqual(number.country_code, 1)
        self.assertEqual(number.national_number, 1234567890)

    def test_parse_with_invalid_number_raises_exception(self):
        with self.assertRaises(PhoneNumberParseException):
            parse_phone_number('qwerty123456')

    def test_parse_with_invalid_number_returns_none_if_failhard_is_false(self):
        number = parse_phone_number('qwerty123456', failhard=False)
        self.assertIsNone(number)

    def test_parse_with_invalid_number_for_region_does_not_raise_exception(self):
        try:
            parse_phone_number('+1(123) 45-6789', region="US")
        except PhoneNumberParseException:
            self.fail("Unexpected exception: phonenumbers lib does not validate for a particular region")

    def test_country_code_for_region_returns_int(self):
        country_code = country_code_for_region('US')
        self.assertEqual(country_code, 1)

    def test_county_code_for_region_returns_zero_if_invalid_region(self):
        country_code = country_code_for_region('invalid')
        self.assertEqual(country_code, 0)

    def test_region_for_country_code_returns_country_name(self):
        # NOTE: returns the first country returned in a list of countries that have this country code
        region = country_name_for_country_code(1)
        self.assertEqual(region, 'United States of America')

    def test_region_for_country_code_returns_empty_string_if_unknown(self):
        region = country_name_for_country_code(0)
        self.assertEqual(region, '')

    def test_get_country_code_and_national_number_returns_successfully(self):
        country_code, national_number = get_country_code_and_national_number("+27123456789")
        self.assertEqual(country_code, 27)
        self.assertEqual(national_number, "123456789")

    def test_get_country_code_and_national_number_returns_none_if_invalid(self):
        country_code, national_number = get_country_code_and_national_number("qwerty123456")
        self.assertIsNone(country_code)
        self.assertIsNone(national_number)
