from django.conf import settings
from django.utils.encoding import smart_str
import pytz
from dimagi.utils.logging import notify_exception

TIMEZONE_DATA_MIGRATION_COMPLETE = False


class _HQTime(object):
    _datetime = None

    def done(self):
        return self._datetime


class _HQTZTime(_HQTime):
    def __init__(self, dt, tzinfo=None):
        if dt.tzinfo is None:
            # assert tzinfo is not None
            self._datetime = dt.replace(tzinfo=tzinfo)
        else:
            # assert tzinfo is None
            self._datetime = dt


class _HQUTCTime(_HQTime):
    def __init__(self, dt):
        # assert dt.tzinfo is None
        self._datetime = dt


class ServerTime(_HQUTCTime):
    def user_time(self, user_tz):
        return UserTime(_adjust_utc_datetime_to_timezone(self._datetime, user_tz))

    def phone_time(self, phone_tz_guess):
        return PhoneTime(_adjust_utc_datetime_to_phone_datetime(self._datetime, phone_tz_guess))


class UserTime(_HQTZTime):
    def server_time(self):
        return ServerTime(_adjust_datetime_to_utc(self._datetime.replace(tzinfo=None), self._datetime.tzinfo))

    def phone_time(self, phone_tz_guess):
        return self.server_time().phone_time(phone_tz_guess)


class PhoneTime(_HQTZTime):
    def server_time(self):
        return ServerTime(_adjust_phone_datetime_to_utc(self._datetime.replace(tzinfo=None), self._datetime.tzinfo))

    def user_time(self, user_tz):
        return self.server_time().user_time(user_tz)


def _adjust_datetime_to_timezone(value, from_tz, to_tz=None):
    """
    Given a ``datetime`` object adjust it according to the from_tz timezone
    string into the to_tz timezone string.
    """
    if to_tz is None:
        to_tz = settings.TIME_ZONE
    if value.tzinfo is None:
        if not hasattr(from_tz, "localize"):
            from_tz = pytz.timezone(smart_str(from_tz))
        value = from_tz.localize(value)
    return value.astimezone(pytz.timezone(smart_str(to_tz)))


def _adjust_datetime_to_utc(value, from_tz):
    """
    Takes a timezone-naive datetime that represents
    something other than a UTC time and converts it to UTC (timezone-aware)

    """
    return _adjust_datetime_to_timezone(value, from_tz, pytz.utc)


def _adjust_utc_datetime_to_timezone(value, to_tz):
    """
    Takes a timezone-naive datetime representing a UTC time

    returns a timezone-aware datetime localized to to_tz
    """
    return _adjust_datetime_to_timezone(value, pytz.utc, to_tz)


def _adjust_phone_datetime_to_utc(value, phone_tz):
    """
    put a phone datetime (like timeEnd, modified_on, etc.) into UTC

    """
    if value.tzinfo is not None:
        # If this happens it's strange and I want to iron it out before
        # timezone migration
        notify_exception(None, 'value passed to adjust_phone_datetime_to_utc '
                               'is not timezone naive: {}'
                               .format(value.tzinfo))
    if TIMEZONE_DATA_MIGRATION_COMPLETE:
        return value
    else:
        return _adjust_datetime_to_utc(value, phone_tz)


def _adjust_utc_datetime_to_phone_datetime(value, phone_tz):
    """
    adjust a UTC datetime so that it's comparable with a phone datetime
    (like timeEnd, modified_on, etc.)

    """
    if value.tzinfo is not None:
        # If this happens it's strange and I want to iron it out before
        # timezone migration
        notify_exception(None, 'value passed to adjust_utc_datetime_to_phone_datetime '
                               'is not timezone naive: {}'
                               .format(value.tzinfo))
    if TIMEZONE_DATA_MIGRATION_COMPLETE:
        return value
    else:
        return _adjust_utc_datetime_to_timezone(value, phone_tz)
