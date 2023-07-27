from corehq.util.timezones.conversions import PhoneTime, ServerTime


def report_date_to_json(date, timezone, date_format, is_phonetime=True):
    if date:
        if is_phonetime:
            user_time = PhoneTime(date, timezone).user_time(timezone)
        else:
            user_time = ServerTime(date).user_time(timezone)
        return user_time.ui_string(date_format)
    else:
        return ''
