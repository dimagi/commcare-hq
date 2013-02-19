from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from corehq.apps.domain.models import Domain
import corehq


register = template.Library()

class MainMenuNode(template.Node):
    def render(self, context):
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
                visible_tabs.append(t)

            if t.is_active:
                active_tab = t

        # set the context variable in the highest scope so it can be used in
        # other blocks
        context.dicts[0]['active_tab'] = active_tab

        return mark_safe(render_to_string("hqwebapp/partials/main_menu.html", {
            'tabs': visible_tabs,
            'active_tab': active_tab,
        }))


@register.tag(name="format_main_menu")
def format_main_menu(parser, token):
    return MainMenuNode()


@register.simple_tag(takes_context=True)
def format_subtab_menu(context):
    active_tab = context.get('active_tab', None)
    if active_tab and active_tab.subtabs:
        subtabs = [t for t in active_tab.subtabs if t.is_viewable]
    else:
        subtabs = None

    return mark_safe(render_to_string("hqwebapp/partials/subtab_menu.html", {
        'subtabs': subtabs if subtabs and len(subtabs) > 1 else None
    }))


@register.simple_tag(takes_context=True)
def format_sidebar(context):
    active_tab = context.get('active_tab', None)
    request = context['request']

    if active_tab and active_tab.subtabs:
        for s in active_tab.subtabs:
            if s.is_active:
                sections = s.sidebar_items
                break
    else:
        sections = active_tab.sidebar_items if active_tab else None

    if sections:
        # set is_active on active sidebar item by modifying nav by reference
        for section_title, navs in sections:
            for nav in navs:
                if request.get_full_path().startswith(nav['url']):
                    nav['is_active'] = True
                else:
                    nav['is_active'] = False

    return mark_safe(render_to_string("hqwebapp/partials/sidebar.html", {
        'sections': sections
    }))
