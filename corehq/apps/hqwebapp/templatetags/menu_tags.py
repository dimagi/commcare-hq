from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from corehq.apps.domain.models import Domain
import corehq.apps.style.utils as style_utils
import corehq


register = template.Library()

class MainMenuNode(template.Node):
    def render(self, context):
        request = context['request']
        current_url_name = context['current_url_name']
        couch_user = getattr(request, 'couch_user', None)
        project = getattr(request, 'project', None)
        domain = context.get('domain')
        org = context.get('org')

        try:
            module = Domain.get_module_by_name(domain)
        except (ValueError, AttributeError):
            module = None

        tabs = corehq.TABS + getattr(module, 'TABS', ())
        visible_tabs = []
        all_tabs = []

        active_tab = None

        for tab_class in tabs:
            t = tab_class(
                    request, current_url_name, domain=domain,
                    couch_user=couch_user, project=project, org=org)

            t.is_active_tab = False
            all_tabs.append(t)
            if t.real_is_viewable:
                visible_tabs.append(t)

        # only highlight the first tab considered active.  This allows
        # multiple tabs to contain the same sidebar item, but in all but
        # the first it will effectively be a link to the other tabs.
        for t in all_tabs:
            if t.is_active_fast:
                t.is_active_tab = True
                active_tab = t
                break

        if active_tab is None:
            for t in all_tabs:
                if t.is_active:
                    t.is_active_tab = True
                    active_tab = t
                    break

        if active_tab is None:
            for t in visible_tabs:
                if t.url and request.get_full_path().startswith(t.url):
                    active_tab = t
                    break

        # set the context variable in the highest scope so it can be used in
        # other blocks
        context.dicts[0]['active_tab'] = active_tab

        template = {
            style_utils.BOOTSTRAP_2: 'hqwebapp/partials/main_menu.html',
            style_utils.BOOTSTRAP_3: 'style/includes/menu_main.html',
        }[style_utils.bootstrap_version(request)]
        return mark_safe(render_to_string(template, {
            'tabs': visible_tabs,
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
        if sections is None:
            for s in active_tab.subtabs:
                if s.url and request.get_full_path().startswith(s.url):
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

                if 'subpages' in nav:
                    for subpage in nav['subpages']:
                        if subpage['urlname'] == current_url_name:
                            if callable(subpage['title']):
                                actual_context = {}
                                for d in context.dicts:
                                    actual_context.update(d)
                                subpage['title'] = subpage['title'](**actual_context)
                            nav['subpage'] = subpage
                            break

    template = {
        style_utils.BOOTSTRAP_2: 'hqwebapp/partials/sidebar.html',
        style_utils.BOOTSTRAP_3: 'style/includes/navigation_left_sidebar.html',
    }[style_utils.bootstrap_version(request)]
    return mark_safe(render_to_string(template, {
        'sections': sections
    }))
