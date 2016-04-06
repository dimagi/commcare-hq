from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

import corehq.apps.style.utils as style_utils
from corehq.tabs import MENU_TABS
from corehq.tabs.utils import path_starts_with_url


register = template.Library()


def _get_active_tab(visible_tabs, request_path):

    matching_tabs = sorted(
        (tab for tab in visible_tabs
         if tab.url and path_starts_with_url(request_path, tab.url)), key=lambda tab: tab.url)

    if matching_tabs:
        return matching_tabs[-1]

    for tab in visible_tabs:
        url_prefixes = tab.url_prefixes
        if url_prefixes:
            if any(path_starts_with_url(url, tab.request_path) for url in url_prefixes):
                return tab


class MainMenuNode(template.Node):
    def render(self, context):
        request = context['request']
        current_url_name = context['current_url_name']
        couch_user = getattr(request, 'couch_user', None)
        project = getattr(request, 'project', None)
        domain = context.get('domain')
        visible_tabs = []
        for tab_class in MENU_TABS:
            t = tab_class(
                request, current_url_name, domain=domain,
                couch_user=couch_user, project=project)

            t.is_active_tab = False
            if t.real_is_viewable:
                visible_tabs.append(t)

        # set the context variable in the highest scope so it can be used in
        # other blocks
        active_tab = context.dicts[0]['active_tab'] = _get_active_tab(
            visible_tabs, request.get_full_path())
        if active_tab:
            active_tab.is_active_tab = True
        return mark_safe(render_to_string('tabs/menu_main.html', {
            'tabs': visible_tabs,
        }))


@register.tag(name="format_main_menu")
def format_main_menu(parser, token):
    return MainMenuNode()


@register.simple_tag(takes_context=True)
def format_sidebar(context):
    current_url_name = context['current_url_name']
    active_tab = context.get('active_tab', None)
    request = context['request']

    sections = active_tab.sidebar_items if active_tab else None

    if sections:
        # set is_active on active sidebar item by modifying nav by reference
        # and see if the nav needs a subnav for the current contextual item
        for section_title, navs in sections:
            for nav in navs:
                full_path = request.get_full_path()
                if path_starts_with_url(full_path, nav['url']):
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
                                subpage['is_active'] = True
                                subpage['title'] = subpage['title'](**actual_context)
                            nav['subpage'] = subpage
                            break

    template = {
        style_utils.BOOTSTRAP_2: 'style/bootstrap2/partials/navigation_left_sidebar.html',
        style_utils.BOOTSTRAP_3: 'style/bootstrap3/partials/navigation_left_sidebar.html',
    }[style_utils.get_bootstrap_version()]
    return mark_safe(render_to_string(template, {
        'sections': sections
    }))
