from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import PhoneTime, ServerTime
from corehq.util.timezones.utils import get_timezone


def report_date_to_json(date, timezone, date_format, is_phonetime=True):
    if date:
        if is_phonetime:
            user_time = PhoneTime(date, timezone).user_time(timezone)
        else:
            user_time = ServerTime(date).user_time(timezone)
        return user_time.ui_string(date_format)
    else:
        return ''
