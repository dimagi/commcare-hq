
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import PhoneTime
from corehq.util.timezones.utils import get_timezone


def report_date_to_json(request, domain, date):
    timezone = get_timezone(request, domain)
    if date:
        return (PhoneTime(date, timezone).user_time(timezone)
                .ui_string(SERVER_DATETIME_FORMAT))
    else:
        return ''
