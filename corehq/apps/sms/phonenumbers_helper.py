

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


def get_country_code_and_national_number(number, failhard=False):
    parsed = parse_phone_number(number, failhard=failhard)
    return (parsed.country_code, parsed.national_number) if parsed else (None, None)
