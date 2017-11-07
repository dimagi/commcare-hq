from __future__ import absolute_import
from django import template
from corehq.apps.domain_migration_flags.api import get_migration_status
from corehq.apps.tzmigration.api import TZMIGRATION_SLUG

register = template.Library()


@register.filter
def tzmigration_status(request):
    if request.domain:
        return get_migration_status(request.domain, TZMIGRATION_SLUG)
    else:
        return None
