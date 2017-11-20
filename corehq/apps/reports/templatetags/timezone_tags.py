from __future__ import absolute_import
from django import template
import pytz
from corehq.util.timezones.conversions import ServerTime
import six

register = template.Library()


@register.simple_tag
def utc_to_timezone(date, timezone):
    if not timezone:
        timezone = pytz.utc
    if not date:
        return "---"
    if isinstance(date, six.string_types):
        raise ValueError("utc_to_timezone no longer accepts strings")
    return ServerTime(date).user_time(timezone).ui_string()
