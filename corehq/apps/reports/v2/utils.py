import datetime
import dateutil
import pytz
from memoized import memoized

from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.dates import iso_string_to_datetime
from corehq.util.timezones.conversions import PhoneTime
from corehq.util.timezones.utils import get_timezone_for_user


@memoized
def get_timezone(request, domain):
    if not domain:
        return pytz.utc
    else:
        try:
            return get_timezone_for_user(request.couch_user, domain)
        except AttributeError:
            return get_timezone_for_user(None, domain)


def parse_date(date_string):
    try:
        return iso_string_to_datetime(date_string)
    except Exception:
        try:
            date_obj = dateutil.parser.parse(date_string)
            if isinstance(date_obj, datetime.datetime):
                return date_obj.replace(tzinfo=None)
            else:
                return date_obj
        except Exception:
            return date_string


def report_date_to_json(request, domain, date):
    timezone = get_timezone(request, domain)
    if date:
        return (PhoneTime(date, timezone).user_time(timezone)
                .ui_string(SERVER_DATETIME_FORMAT))
    else:
        return ''
