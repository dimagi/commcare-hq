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
    module = Domain.get_module_by_name(domain)
    
    menu_items = corehq.MENU_ITEMS + getattr(module, 'MENU_ITEMS', ())

    menu_context = [menu_item(request, domain).menu_context
                    for menu_item in menu_items
                    if menu_item.is_viewable(request, domain)]
    
    return mark_safe(render_to_string(menu_template, {
        'menu_items': menu_context,
    }))
