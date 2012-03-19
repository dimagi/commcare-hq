import types
from datetime import date, datetime
from django import template
from django.utils.html import escape
import pytz
from casexml.apps.case.models import CommCareCase
from django.template.loader import render_to_string
from couchdbkit.exceptions import ResourceNotFound

register = template.Library()

@register.simple_tag
def render_case(case, timezone=pytz.utc):
    if isinstance(case, basestring):
        # we were given an ID, fetch the case
        case = CommCareCase.get(case)
    
    return render_to_string("case/partials/single_case.html", {"case": case, "timezone": timezone})
    
    
@register.simple_tag
def case_inline_display(case):
    """
    Given a case id, make a best effort at displaying it.
    """
    if case:
        if case.opened_on:
            return "%s (opened: %s)" % (case.name, case.opened_on.date())
        else:
            return case.name
    return "empty case" 
    