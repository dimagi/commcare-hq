from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from corehq.apps.domain.models import Domain
import corehq.apps.style.utils as style_utils
import corehq
from corehq.apps.hqwebapp.models import MaintenanceAlert

register = template.Library()


def get_active_tab(visible_tabs, request_path):
    for is_active_tab_fn in [
        lambda t: t.is_active_fast,
        lambda t: t.is_active,
        lambda t: t.url and request_path.startswith(t.url),
    ]:
        for tab in visible_tabs:
            if is_active_tab_fn(tab):
                tab.is_active_tab = True
                return tab


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

        tabs = getattr(module, 'TABS', corehq.TABS)
        visible_tabs = []
        for tab_class in tabs:
            t = tab_class(
                    request, current_url_name, domain=domain,
                    couch_user=couch_user, project=project, org=org)

            t.is_active_tab = False
            if t.real_is_viewable:
                visible_tabs.append(t)

        # set the context variable in the highest scope so it can be used in
        # other blocks
        context.dicts[0]['active_tab'] = get_active_tab(visible_tabs,
                                                        request.get_full_path())

        template = {
            style_utils.BOOTSTRAP_2: 'style/bootstrap2/partials/menu_main.html',
            style_utils.BOOTSTRAP_3: 'style/bootstrap3/partials/menu_main.html',
        }[style_utils.get_bootstrap_version()]
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
                if (request.get_full_path().startswith(nav['url']) or
                   request.build_absolute_uri().startswith(nav['url'])):
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
        style_utils.BOOTSTRAP_2: 'style/bootstrap2/partials/navigation_left_sidebar.html',
        style_utils.BOOTSTRAP_3: 'style/bootstrap3/partials/navigation_left_sidebar.html',
    }[style_utils.get_bootstrap_version()]
    return mark_safe(render_to_string(template, {
        'sections': sections
    }))


@register.simple_tag
def maintenance_alert():
    try:
        alert = (MaintenanceAlert.objects
                 .filter(active=True)
                 .order_by('-modified'))[0]
    except IndexError:
        return ''
    else:
        return format_html(
            '<div class="alert alert-warning" style="text-align: center; margin-bottom: 0;">{}</div>',
            mark_safe(alert.html),
        )
