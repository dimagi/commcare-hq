

class PhoneNumberParseException(Exception):
    pass


class PhoneNumber(object):
    def __init__(self, country_code, national_number):
        self.country_code = country_code
        self.national_number = national_number

def parse_phone_number(number, region=None, keep_raw_input=False,
                      numobj=None, _check_region=True, failhard=True):
    from phonenumbers.phonenumberutil import parse as phonenumbers_parse, NumberParseException
    try:
        phone = phonenumbers_parse(number, region, keep_raw_input, numobj, _check_region)
        if phone:
            return PhoneNumber(phone.country_code, phone.national_number)
    except NumberParseException:
        if failhard:
            raise PhoneNumberParseException()
        else:
            return None
