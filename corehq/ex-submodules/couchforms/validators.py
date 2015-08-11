from iso8601 import iso8601
from couchforms.exceptions import PhoneDateValueError


def validate_phone_datetime(datetime_string, none_ok=False):
    if datetime_string is None and none_ok:
        return None
    try:
        return iso8601.parse_date(datetime_string)
    except iso8601.ParseError:
        raise PhoneDateValueError('{!r}'.format(datetime_string))
