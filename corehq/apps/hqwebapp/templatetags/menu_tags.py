from django import template
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from dimagi.utils.modules import to_function

register = template.Library()

@register.simple_tag(takes_context=True)
def format_main_menu(context):
    menu_template="hqwebapp/partials/main_menu.html"
    menu_items = settings.MENU_ITEMS
    menu_context = []
    request = context['request']
    domain = context.get('domain')
    for m in menu_items:
        menu_item_class = to_function(m)
        try:
            viewable = menu_item_class.is_viewable(request, domain)
        except AttributeError:
            viewable = False
        if viewable:
            menu_item = menu_item_class(request, domain)
            menu_context.append(menu_item.menu_context)
    return mark_safe(render_to_string(menu_template, {
        'menu_items': menu_context,
    }))