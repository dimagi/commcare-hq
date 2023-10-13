from corehq.apps.users.models import DomainMembershipError
from django import template
from django.template.loader import render_to_string
from django.utils.translation import get_language

from corehq.tabs.config import MENU_TABS
from corehq.tabs.exceptions import TabClassError, TabClassErrorSummary
from corehq.tabs.extension_points import uitab_classes
from corehq.tabs.utils import path_starts_with_url
from corehq.tabs.uitab import UITab


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
    tab_classes = list(MENU_TABS)
    tab_classes.extend(uitab_classes())
    for tab_class in tab_classes:
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
            '- {}: {}'.format(e.__class__.__name__, str(e))
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
        role_version = None
        try:
            if couch_user:
                user_role = couch_user.get_role(domain, allow_enterprise=True)
                role_version = user_role.cache_version if user_role else None
        except DomainMembershipError:
            role_version = None

        lang = get_language()

        from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version, BOOTSTRAP_5
        bootstrap_version = get_bootstrap_version()
        use_bootstrap5 = bootstrap_version == BOOTSTRAP_5

        for tab in visible_tabs:
            tab.frag_value = UITab.create_compound_cache_param(
                tab.class_name(),
                domain,
                couch_user._id,
                role_version,
                tab.is_active_tab,
                lang,
                use_bootstrap5
            )

        context.dicts[0]['active_tab'] = active_tab
        flat = context.flatten()
        flat.update({
            'tabs': visible_tabs,
            'role_version': role_version,
            'use_bootstrap5': use_bootstrap5,
        })
        return render_to_string(f"tabs/{bootstrap_version}/menu_main.html", flat)


@register.tag(name="format_main_menu")
def format_main_menu(parser, token):
    return MainMenuNode()


@register.simple_tag(takes_context=True)
def format_sidebar(context):
    current_url_name = context['current_url_name']
    active_tab = context.get('active_tab', None)
    request = context['request']

    sections = active_tab.filtered_sidebar_items if active_tab else None

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

    from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version
    return render_to_string(
        f"hqwebapp/partials/{get_bootstrap_version()}/navigation_left_sidebar.html",
        {'sections': sections}
    )
