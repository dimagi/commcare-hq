from __future__ import absolute_import
from __future__ import unicode_literals
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
    if isinstance(date, (six.text_type, bytes)):
        raise ValueError("utc_to_timezone no longer accepts strings")
    return ServerTime(date).user_time(timezone).ui_string()
