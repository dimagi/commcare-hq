from django import template
from corehq.apps import tzmigration

register = template.Library()


@register.filter
def tzmigration_status(request):
    if request.domain:
        return tzmigration.get_migration_status(request.domain)
    else:
        return None
