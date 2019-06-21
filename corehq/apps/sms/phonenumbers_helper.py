

from __future__ import absolute_import
from __future__ import unicode_literals


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
        if phone:
            return PhoneNumber(phone.country_code, phone.national_number)
    except NumberParseException:
        if failhard:
            raise PhoneNumberParseException()
        else:
            return None


def strip_plus(number):
    return number[1:] if number.startswith('+') else number


def get_country_code_and_national_number(number, failhard=False):
    parsed = parse_phone_number(number, failhard=failhard)
    if parsed:
        country_code = parsed.country_code
        national_number = strip_plus(number)[len(str(country_code)):]
        return country_code, national_number
    return None, None
