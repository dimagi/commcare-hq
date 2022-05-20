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


def get_country_code_and_national_number(number, failhard=False):
    parsed = parse_phone_number(number, failhard=failhard)
    if parsed:
        country_code = parsed.country_code
        national_number = strip_plus(number)[len(str(country_code)):]
        return country_code, national_number
    return None, None


def country_code_for_region(region):
    """
    Simple wrapper around phonenumbers country_code_for_region method
    :param region: str (examples: 'US', 'IN', 'ZA')
    :return: int
    """
    from phonenumbers import country_code_for_region as phonenumbers_country_code_for_region
    return phonenumbers_country_code_for_region(region)
