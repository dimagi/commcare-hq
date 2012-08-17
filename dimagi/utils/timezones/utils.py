from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.encoding import smart_str
import pytz
import datetime
import dateutil

def localtime_for_timezone(value, timezone):
    """
    Given a ``datetime.datetime`` object in UTC and a timezone represented as
    a string, return the localized time for the timezone.
    """
    return adjust_datetime_to_timezone(value, settings.TIME_ZONE, timezone)

def adjust_datetime_to_timezone(value, from_tz, to_tz=None):
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

def coerce_timezone_value(value):
    try:
        return pytz.timezone(str(value))
    except pytz.UnknownTimeZoneError:
        raise ValidationError("Unknown timezone")

def validate_timezone_max_length(max_length, zones):
    def reducer(x, y):
        return x and (len(y) <= max_length)
    if not reduce(reducer, zones, True):
        raise Exception("corehq.apps.timezones.fields.TimeZoneField MAX_TIMEZONE_LENGTH is too small")

def string_to_prertty_time(date_string, to_tz, from_tz=pytz.utc, fmt="%b %d, %Y %H:%M"):
    try:
        date = datetime.datetime.replace(dateutil.parser.parse(date_string), tzinfo=from_tz)
        date = adjust_datetime_to_timezone(date, from_tz.zone, to_tz.zone)
        return date.strftime(fmt)
    except Exception:
        return date_string

def is_timezone_in_dst(tz, compare_time=None):
    now = datetime.datetime.now(tz=tz) if not compare_time else tz.localize(compare_time)
    transitions = []
    for dst_transition in tz._utc_transition_times:
        if dst_transition.year == now.year:
            transitions.append(tz.localize(dst_transition))
    if len(transitions) >= 2 and (transitions[0] <= now <= transitions[1]):
        return True
    return False