from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import PhoneTime, ServerTime
from corehq.util.timezones.utils import get_timezone


def report_date_to_json(request, domain, date, is_phonetime=True):
    timezone = get_timezone(request, domain)
    if date:
        if is_phonetime:
            user_time = PhoneTime(date, timezone).user_time(timezone)
        else:
            user_time = ServerTime(date).user_time(timezone)
        user_time.ui_string(SERVER_DATETIME_FORMAT)
    else:
        return ''
