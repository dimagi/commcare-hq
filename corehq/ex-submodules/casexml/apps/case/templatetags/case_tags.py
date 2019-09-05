from django import template
from django.utils.translation import ugettext as _
from django.utils.html import escape

from couchdbkit import ResourceNotFound

register = template.Library()


@register.simple_tag
def case_inline_display(case):
    """
    Given a case id, make a best effort at displaying it.
    """
    if case:
        if case.opened_on:
            ret = "%s (%s: %s)" % (case.name, _("Opened"), case.opened_on.date())
        else:
            ret = case.name
    else:
        ret = _("Empty Case")

    return escape(ret)
