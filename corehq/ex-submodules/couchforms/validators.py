from iso8601 import iso8601
from corehq.util.soft_assert import soft_assert
from couchforms.exceptions import PhoneDateValueError

_soft_assert = soft_assert('@'.join(['droberts', 'dimagi.com']))


def validate_phone_datetime(datetime_string, none_ok=False):
    if none_ok:
        if datetime_string is None:
            return None
        if not _soft_assert(datetime_string != '',
                            'phone datetime should never be empty'):
            return None
    try:
        return iso8601.parse_date(datetime_string)
    except iso8601.ParseError:
        raise PhoneDateValueError('{!r}'.format(datetime_string))
