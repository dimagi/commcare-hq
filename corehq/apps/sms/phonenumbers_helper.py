from django.utils.encoding import force_str
from django_countries.data import COUNTRIES


class PhoneNumberParseException(Exception):
    pass


class PhoneNumber(object):

    def __init__(self, country_code, national_number):
        self.country_code = country_code
        self.national_number = national_number


def parse_phone_number(number, region=None, failhard=True):
    from phonenumbers.phonenumberutil import parse as phonenumbers_parse, NumberParseException
    try:
        phone = phonenumbers_parse(number, region)
    except NumberParseException:
        if failhard:
            raise PhoneNumberParseException()
        else:
            return None

    return PhoneNumber(phone.country_code, phone.national_number)


def strip_plus(number):
    return number[1:] if number.startswith('+') else number


def get_country_code_and_national_number(number):
    """
    :param number: str representing phone number
    :return: country_code: int, national_number: str or, if the number
    could not be parsed, `None, None`.
    """
    parsed = parse_phone_number(number, failhard=False)
    return (parsed.country_code, str(parsed.national_number)) if parsed else (None, None)


def country_code_for_region(region):
    """
    Simple wrapper around phonenumbers country_code_for_region method
    :param region: str (examples: 'US', 'IN', 'ZA')
    :return: int, 0 if invalid, country code if valid
    """
    from phonenumbers import country_code_for_region as phonenumbers_country_code_for_region
    return phonenumbers_country_code_for_region(region)


def country_name_for_country_code(country_code):
    """
    Blindly returns the first country in a list of countries that the country_code maps to
    :param country_code: integer representing country code in a phone number
    :return: first country returned from phonenumbers mapping
    """
    from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
    regions = COUNTRY_CODE_TO_REGION_CODE.get(country_code)
    return force_str(COUNTRIES.get(regions[0])) if regions else ''
