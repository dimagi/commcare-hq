from django import template
import pytz
from corehq.apps.reports import standard
from dimagi.utils.timezones import utils as tz_utils
import datetime

register = template.Library()

@register.simple_tag
def utc_to_timezone(date, timezone, dest_fmt="%b %d, %Y %H:%M %Z", src_fmt=standard.DATE_FORMAT):

    if not isinstance(date, datetime.datetime):
        try:
            date = datetime.datetime.strptime(date, src_fmt)
        except ValueError:
            return date
    return tz_utils.adjust_datetime_to_timezone(date, date.tzname(), timezone.zone).strftime(dest_fmt)