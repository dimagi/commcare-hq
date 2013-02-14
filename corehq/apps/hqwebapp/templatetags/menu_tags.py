from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from corehq.apps.domain.models import Domain
import corehq

register = template.Library()

@register.simple_tag(takes_context=True)
def format_main_menu(context):
    request = context['request']
    domain = context.get('domain')
    couch_user = getattr(request, 'couch_user', None)
    project = getattr(request, 'project', None)

    module = Domain.get_module_by_name(domain)

    tabs = corehq.TABS + getattr(module, 'TABS', ())
    visible_tabs = []
    active_tab = None

    for tab_class in tabs:
        t = tab_class(
                request, domain=domain, couch_user=couch_user, project=project)

        if t.real_is_viewable:
            print "foo", t
            visible_tabs.append(t)

        if t.is_active:
            active_tab = t

    return mark_safe(render_to_string("hqwebapp/partials/main_menu.html", {
        'tabs': visible_tabs,
        'active_tab': active_tab,
    }))


@register.simple_tag(takes_context=True)
def format_subtab_menu(context):
    return mark_safe('')
    # todo (active_tab is already used in dimagi-utils' render_to_response)
    active_tab = context['active_tab']

    # todo: active tab
    if True or not (active_tab and active_tab.has_subtabs):
        return mark_safe('')
   
    # todo
    subtabs = active_tab.sidebar_items if active_tab.has_subtabs else None

    return mark_safe(render_to_string("hqwebapp/partials/subtab_menu.html", {
        'subtabs': subtabs
    }))

