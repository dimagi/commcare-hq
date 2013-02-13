from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from corehq.apps.domain.models import Domain
import corehq

register = template.Library()

@register.simple_tag(takes_context=True)
def format_main_menu(context):
    menu_template = "hqwebapp/partials/main_menu.html"
    request = context['request']
    domain = context.get('domain')
    couch_user = getattr(request, 'couch_user', None)
    project = getattr(request, 'project', None)

    module = Domain.get_module_by_name(domain)
    
    menu_items = corehq.MENU_ITEMS + getattr(module, 'MENU_ITEMS', ())
    visible_items = []
    
    for menu_item in menu_items:
        m = menu_item(
                request, domain=domain, couch_user=couch_user, project=project)

        if m.is_viewable:
            visible_items.append(m)
    
    return mark_safe(render_to_string(menu_template, {
        'menu_items': (m.menu_context for m in visible_items),
    }))
