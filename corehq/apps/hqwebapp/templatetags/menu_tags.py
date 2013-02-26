from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from corehq.apps.domain.models import Domain
import corehq


register = template.Library()

class MainMenuNode(template.Node):
    def render(self, context):
        request = context['request']
        couch_user = getattr(request, 'couch_user', None)
        project = getattr(request, 'project', None)
        domain = context.get('domain')
        
        try:
            module = Domain.get_module_by_name(domain)
        except (ValueError, AttributeError):
            module = None

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
    current_url_name = context['current_url_name']
    active_tab = context.get('active_tab', None)
    request = context['request']

    sections = None

    if active_tab and active_tab.subtabs:
        # if active_tab is active then at least one of its subtabs should have
        # is_active == True, but we guard against the possibility of this not
        # being the case by setting sections = None above
        for s in active_tab.subtabs:
            if s.is_active:
                sections = s.sidebar_items
                break
    else:
        sections = active_tab.sidebar_items if active_tab else None

    if sections:
        # set is_active on active sidebar item by modifying nav by reference
        # and see if the nav needs a subnav for the current contextual item
        for section_title, navs in sections:
            for nav in navs:
                if request.get_full_path().startswith(nav['url']):
                    nav['is_active'] = True
                else:
                    nav['is_active'] = False

                if 'children' in nav:
                    for child in nav['children']:
                        if child['urlname'] == current_url_name:
                            if callable(child['title']):
                                actual_context = {}
                                for d in context.dicts:
                                    actual_context.update(d)
                                child['title'] = child['title'](**actual_context)
                            nav['child'] = child
                            break

    return mark_safe(render_to_string("hqwebapp/partials/sidebar.html", {
        'sections': sections
    }))
