from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

import corehq.apps.style.utils as style_utils
from corehq.tabs import MENU_TABS
from corehq.tabs.exceptions import TabClassError, TabClassErrorSummary
from corehq.tabs.utils import path_starts_with_url


register = template.Library()


def _get_active_tab(visible_tabs, request_path):
    """
    return the tab that claims the longest matching url_prefix

    if one tab claims
      '/a/{domain}/data/'
    and another tab claims
      '/a/{domain}/data/edit/case_groups/'
    then the second tab wins because it's a longer match.

    """

    matching_tabs = sorted(
        (url_prefix, tab)
        for tab in visible_tabs
        for url_prefix in tab.url_prefixes
        if request_path.startswith(url_prefix)
    )

    if matching_tabs:
        _, tab = matching_tabs[-1]
        return tab


def get_all_tabs(request, domain, couch_user, project):
    """
    instantiate all UITabs, and aggregate all their TabClassErrors (if any)
    into a single TabClassErrorSummary

    this makes it easy to get a list of all configuration issues
    and fix them in one cycle

    """
    all_tabs = []
    instantiation_errors = []
    for tab_class in MENU_TABS:
        try:
            tab = tab_class(
                request, domain=domain,
                couch_user=couch_user, project=project)
        except TabClassError as e:
            instantiation_errors.append(e)
        else:
            all_tabs.append(tab)

    if instantiation_errors:
        messages = (
            '- {}: {}'.format(e.__class__.__name__, e.message)
            for e in instantiation_errors
        )
        summary_message = 'Summary of Tab Class Errors:\n{}'.format('\n'.join(messages))
        raise TabClassErrorSummary(summary_message)
    else:
        return all_tabs


class MainMenuNode(template.Node):
    def render(self, context):
        request = context['request']
        couch_user = getattr(request, 'couch_user', None)
        project = getattr(request, 'project', None)
        domain = context.get('domain')

        all_tabs = get_all_tabs(request, domain=domain, couch_user=couch_user,
                                project=project)

        active_tab = _get_active_tab(all_tabs, request.get_full_path())

        if active_tab:
            active_tab.is_active_tab = True

        visible_tabs = [tab for tab in all_tabs if tab.should_show()]

        # set the context variable in the highest scope so it can be used in
        # other blocks
        context.dicts[0]['active_tab'] = active_tab
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
