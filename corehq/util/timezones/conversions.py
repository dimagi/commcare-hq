from django.utils.encoding import smart_str
import pytz
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.dates import safe_strftime


# The timezone data migration happening some time in Apr-May 2015
# will shift all phone times (form.timeEnd, case.modified_on, etc.) to UTC
# so functions that deal with converting to or from phone times
# use this variable to decide what type of timezone conversion is necessary
from dimagi.utils.logging import notify_exception, get_traceback

TIMEZONE_DATA_MIGRATION_COMPLETE = False


class _HQTime(object):
    _datetime = None

    def done(self):
        return self._datetime


class _HQTZTime(_HQTime):
    def __init__(self, dt, tzinfo=None):
        if dt.tzinfo is None:
            assert tzinfo is not None
            tzinfo = _soft_assert_tz_not_string(tzinfo)
            self._datetime = dt.replace(tzinfo=tzinfo)
        else:
            assert tzinfo is None
            self._datetime = dt


class _HQUTCTime(_HQTime):
    def __init__(self, dt):
        assert dt.tzinfo is None
        self._datetime = dt


class ServerTime(_HQUTCTime):
    def user_time(self, user_tz):
        return UserTime(_adjust_utc_datetime_to_timezone(
            self._datetime, user_tz))

    def phone_time(self, phone_tz_guess):
        return PhoneTime(_adjust_utc_datetime_to_phone_datetime(
            self._datetime, phone_tz_guess))


class UserTime(_HQTZTime):
    def server_time(self):
        return ServerTime(_adjust_datetime_to_utc(
            self._datetime.replace(tzinfo=None), self._datetime.tzinfo))

    def phone_time(self, phone_tz_guess):
        return self.server_time().phone_time(phone_tz_guess)

    def ui_string(self, fmt=USER_DATETIME_FORMAT):
        return safe_strftime(self._datetime, fmt)


class PhoneTime(_HQTZTime):
    def server_time(self):
        return ServerTime(_adjust_phone_datetime_to_utc(
            self._datetime.replace(tzinfo=None), self._datetime.tzinfo))

    def user_time(self, user_tz):
        return self.server_time().user_time(user_tz)

    def done(self):
        # phone times should always come out timezone naive
        # clobbering the timezone without adjusting to UTC
        return self._datetime.replace(tzinfo=None)


def _soft_assert_tz_not_string(tz):
    try:
        assert hasattr(tz, "localize")
    except AssertionError:
        # tz is a string, or at least string-like
        # todo: log to figure out where this happens and fix
        return pytz.timezone(smart_str(tz))
    else:
        return tz


def _adjust_datetime_to_utc(value, from_tz):
    """
    Takes a timezone-naive datetime that represents
    something other than a UTC time and converts it to UTC (timezone-naive)

    """
    from_tz = _soft_assert_tz_not_string(from_tz)
    assert value.tzinfo is None
    return from_tz.localize(value).astimezone(pytz.utc).replace(tzinfo=None)


def _adjust_utc_datetime_to_timezone(value, to_tz):
    """
    Takes a timezone-naive datetime representing a UTC time

    returns a timezone-aware datetime localized to to_tz
    """
    to_tz = _soft_assert_tz_not_string(to_tz)
    assert value.tzinfo is None
    return pytz.utc.localize(value).astimezone(to_tz)


def _adjust_phone_datetime_to_utc(value, phone_tz):
    """
    put a phone datetime (like timeEnd, modified_on, etc.) into UTC

    input and output are both timezone-naive

    """
    phone_tz = _soft_assert_tz_not_string(phone_tz)
    assert value.tzinfo is None
    if TIMEZONE_DATA_MIGRATION_COMPLETE:
        return value
    else:
        return _adjust_datetime_to_utc(value, phone_tz)


def _adjust_utc_datetime_to_phone_datetime(value, phone_tz):
    """
    adjust a UTC datetime so that it's comparable with a phone datetime
    (like timeEnd, modified_on, etc.)

    returns a timezone-aware date

    """
    phone_tz = _soft_assert_tz_not_string(phone_tz)
    assert value.tzinfo is None
    if TIMEZONE_DATA_MIGRATION_COMPLETE:
        return value.replace(tzinfo=pytz.utc)
    else:
        return _adjust_utc_datetime_to_timezone(value, phone_tz)
