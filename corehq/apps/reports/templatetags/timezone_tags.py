import dateutil
from django import template
import pytz
from corehq.util.timezones import utils as tz_utils
import datetime

register = template.Library()


@register.simple_tag
def utc_to_timezone(date, timezone, dest_fmt="%b %d, %Y %H:%M %Z"):
    if not timezone:
        timezone = pytz.utc
    if not date:
        return "---"
    if not isinstance(date, datetime.datetime):
        try:
            date = datetime.datetime.replace(dateutil.parser.parse(date), tzinfo=pytz.utc)
        except Exception as e:
            return date
    return tz_utils.adjust_utc_datetime_to_timezone(date, timezone.zone).strftime(dest_fmt)
