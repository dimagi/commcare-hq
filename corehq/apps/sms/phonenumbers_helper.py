

class PhoneNumberParseException(Exception):
    pass


def parse_phone_number(number, region=None, keep_raw_input=False,
                      numobj=None, _check_region=True, failhard=True):
    from phonenumbers.phonenumberutil import parse as phonenumbers_parse, NumberParseException
    try:
        return phonenumbers_parse(number, region, keep_raw_input, numobj, _check_region)
    except NumberParseException:
        if failhard:
            raise PhoneNumberParseException()
        else:
            return None
