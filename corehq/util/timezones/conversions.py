from django.utils.encoding import smart_str
import pytz
from corehq.const import USER_DATETIME_FORMAT
from corehq.toggles import USE_NEW_TIMEZONE_BEHAVIOR
from corehq.util.soft_assert import soft_assert
from corehq.util.view_utils import get_request
from dimagi.utils.dates import safe_strftime


def get_timezone_data_migration_complete():
    """
    The timezone data migration happening some time in Apr-May 2015
    will shift all phone times (form.timeEnd, case.modified_on, etc.) to UTC
    so functions that deal with converting to or from phone times
    use this function to decide what type of timezone conversion is necessary

    """
    _default = False
    _assert = soft_assert(['droberts' + '@' + 'dimagi.com'])
    try:
        request = get_request()
        try:
            domain = request.domain
        except AttributeError:
            return _default
        return USE_NEW_TIMEZONE_BEHAVIOR.enabled(domain)
    except Exception:
        _assert(False, 'Error in get_timezone_data_migration_complete')
        return _default


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
    _assert = soft_assert(to=['droberts@dimagi.com'], skip_frames=1)

    if not _assert(hasattr(tz, "localize"),
                   'Timezone should be a tzinfo object, not a string'):
        # tz is a string, or at least string-like
        return pytz.timezone(smart_str(tz))
    else:
        return tz


def _adjust_datetime_to_utc(value, from_tz):
    """
    Takes a timezone-naive datetime that represents
    something other than a UTC time and converts it to UTC (timezone-naive)

    In timezones with DST, there is one hour per year where a time plus
    timezone (i.e. 'America/New_York' w/o specifying EST vs EDT)
    could represent one of two actual points in time, separated by an hour.
    This function does not attempt to deal with the
    (literally impossible) problem of figuring out which was intended,
    and simply returns one arbitrarily.
    (This is of course one of many reasons that storing datetimes
    as timezone-naive local wall-clock times is, always, a very bad idea.)

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
    if get_timezone_data_migration_complete():
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
    if get_timezone_data_migration_complete():
        return value.replace(tzinfo=pytz.utc)
    else:
        return _adjust_utc_datetime_to_timezone(value, phone_tz)
