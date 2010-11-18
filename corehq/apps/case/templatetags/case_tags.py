import types
from datetime import date, datetime
from django import template
from corehq.apps.xforms.util import value_for_display

register = template.Library()

@register.simple_tag
def format_case(case):
    template = '<span class="%(status)s">%(status)s: %(modifier)s</span>'
    status = "closed" if case.closed else "open"
    return template % {"status": status, "modifier": case.status_display()}