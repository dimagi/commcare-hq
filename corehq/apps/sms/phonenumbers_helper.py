import settings


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


def get_country_code_or_prefix(number, failhard=False):
    parsed = parse_phone_number(number, failhard=failhard)

    if not parsed:
        return None

    prefix = get_prefix(parsed)
    if prefix:
        return prefix

    return parsed.country_code


def get_prefix(parsed_number, sms_prefixes_by_country=settings.SMS_PREFIXES_BY_COUNTRY):
    if parsed_number.country_code in sms_prefixes_by_country:
        number_str = str(parsed_number.country_code) + str(parsed_number.national_number)
        for prefix in sms_prefixes_by_country[parsed_number.country_code]:
            if number_str.startswith(str(prefix)):
                return prefix
    return None
