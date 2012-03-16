from django import template
from corehq.apps.reports import standard
import datetime

register = template.Library()

@register.simple_tag
def utc_to_timezone(timezone, str_fmt=standard.DATE_FORMAT):
    # there has to be a better way to do this
