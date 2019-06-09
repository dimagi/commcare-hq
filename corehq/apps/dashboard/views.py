from __future__ import absolute_import, division
from __future__ import unicode_literals
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.utils.translation import ugettext_noop, ugettext as _

import math

from corehq import privileges
from corehq.apps.accounting.mixins import BillingModalsMixin
from corehq.apps.app_manager.dbaccessors import domain_has_apps, get_brief_apps_in_domain
from corehq.apps.dashboard.models import (
    AppsPaginator,
    DataPaginator,
    ReportsPaginator,
    Tile,
    Tile,
)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import DomainViewMixin, LoginAndDomainMixin
from corehq.apps.domain.views.settings import DefaultProjectSettingsView
from corehq.apps.domain.utils import user_has_custom_top_menu
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
from corehq.apps.users.views import DefaultProjectUserSettingsView
from corehq.apps.locations.permissions import location_safe, user_can_edit_location_types
from corehq.util.context_processors import commcare_hq_names
from dimagi.utils.web import json_response
from django_prbac.utils import has_privilege


@login_and_domain_required
@location_safe
def dashboard_default(request, domain):
    return HttpResponseRedirect(default_dashboard_url(request, domain))


def default_dashboard_url(request, domain):
    couch_user = getattr(request, 'couch_user', None)

    if domain in settings.CUSTOM_DASHBOARD_PAGE_URL_NAMES:
        return reverse(settings.CUSTOM_DASHBOARD_PAGE_URL_NAMES[domain], args=[domain])

    if couch_user and user_has_custom_top_menu(domain, couch_user):
        return reverse('saved_reports', args=[domain])

    if not domain_has_apps(domain):
        return reverse('default_app', args=[domain])

    return reverse(DomainDashboardView.urlname, args=[domain])


def _get_tile(request, slug):
    try:
        tile = [t for t in _get_default_tiles(request) if t.slug == slug][0]
    except IndexError:
        raise Http404()

    return tile


@login_and_domain_required
@location_safe
def dashboard_tile(request, domain, slug):
    tile = _get_tile(request, slug)
    current_page = int(request.GET.get('currentPage', 1))
    items_per_page = int(request.GET.get('itemsPerPage', 5))
    items = list(tile.paginator.paginated_items(current_page, items_per_page))
    return json_response({'items': items})


@login_and_domain_required
@location_safe
def dashboard_tile_total(request, domain, slug):
    tile = _get_tile(request, slug)
    return json_response({'total': tile.paginator.total})


@location_safe
class DomainDashboardView(LoginAndDomainMixin, BillingModalsMixin, BasePageView, DomainViewMixin):
    urlname = 'dashboard_domain'
    page_title = ugettext_noop("HQ Dashboard")
    template_name = 'dashboard/base.html'

    @property
    def main_context(self):
        context = super(DomainDashboardView, self).main_context
        context.update({
            'domain': self.domain,
        })
        return context

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        tile_contexts = []
        for tile in _get_default_tiles(self.request):
            if tile.is_visible:
                tile_context = {
                    'title': tile.title,
                    'slug': tile.slug,
                    'icon': tile.icon,
                    'url': tile.get_url(self.request),
                    'help_text': tile.help_text,
                }
                if tile.paginator_class:
                    tile_context.update({
                        'has_item_list': True,
                    })
                tile_contexts.append(tile_context)
        return {'dashboard_tiles': tile_contexts}


def _get_default_tiles(request):
    can_edit_data = lambda request: (request.couch_user.can_edit_data()
                                     or request.couch_user.can_access_any_exports())
    can_edit_apps = lambda request: (request.couch_user.is_web_user()
                                     or request.couch_user.can_edit_apps())
    can_view_reports = lambda request: user_can_view_reports(request.project, request.couch_user)
    can_edit_users = lambda request: (request.couch_user.can_edit_commcare_users()
                                      or request.couch_user.can_edit_web_users())

    def can_edit_locations_not_users(request):
        if not has_privilege(request, privileges.LOCATIONS):
            return False
        user = request.couch_user
        return not can_edit_users(request) and (
            user.can_edit_locations() or user_can_edit_location_types(user, request.domain)
        )

    can_view_commtrack_setup = lambda request: (request.project.commtrack_enabled)

    def can_view_exchange(request):
        return (
            can_edit_apps(request)
            and not settings.ENTERPRISE_MODE
            and not get_domain_master_link(request.domain)  # this isn't a linked domain
        )

    def _can_access_sms(request):
        return has_privilege(request, privileges.OUTBOUND_SMS)

    def _can_access_reminders(request):
        return has_privilege(request, privileges.REMINDERS_FRAMEWORK)

    can_use_messaging = lambda request: (
        (_can_access_reminders(request) or _can_access_sms(request))
        and not request.couch_user.is_commcare_user()
        and request.couch_user.can_edit_data()
    )

    is_billing_admin = lambda request: request.couch_user.can_edit_billing()
    apps_link = lambda urlname, req: (
        '' if domain_has_apps(request.domain)
        else reverse(urlname, args=[request.domain])
    )

    commcare_name = commcare_hq_names(request)['commcare_hq_names']['COMMCARE_NAME']

    return [
        Tile(
            request,
            title=_('Applications'),
            slug='applications',
            icon='fcc fcc-applications',
            paginator_class=AppsPaginator,
            visibility_check=can_edit_apps,
            urlname='default_new_app',
            url_generator=apps_link,
            help_text=_('Build, update, and deploy applications'),
        ),
        Tile(
            request,
            title=_('Reports'),
            slug='reports',
            icon='fcc fcc-reports',
            paginator_class=ReportsPaginator,
            urlname='reports_home',
            visibility_check=can_view_reports,
            help_text=_('View worker monitoring reports and inspect project data'),
        ),
        Tile(
            request,
            title=_('{cc_name} Supply Setup').format(cc_name=commcare_name),
            slug='commtrack_setup',
            icon='fcc fcc-commtrack',
            urlname='default_commtrack_setup',
            visibility_check=can_view_commtrack_setup,
            help_text=_("Update {cc_name} Supply Settings").format(cc_name=commcare_name),
        ),
        Tile(
            request,
            title=_('Data'),
            slug='data',
            icon='fcc fcc-data',
            paginator_class=DataPaginator,
            urlname="data_interfaces_default",
            visibility_check=can_edit_data,
            help_text=_('Export and manage data'),
        ),
        Tile(
            request,
            title=_('Users'),
            slug='users',
            icon='fcc fcc-users',
            urlname=DefaultProjectUserSettingsView.urlname,
            visibility_check=can_edit_users,
            help_text=_('Manage accounts for mobile workers and CommCareHQ users'),
        ),
        Tile(
            request,
            title=_('Organization'),
            slug='locations',
            icon='fcc fcc-users',
            urlname='default_locations_view',
            visibility_check=can_edit_locations_not_users,
            help_text=_('Manage the Organization Hierarchy'),
        ),
        Tile(
            request,
            title=_('Messaging'),
            slug='messaging',
            icon='fcc fcc-messaging',
            urlname='sms_default',
            visibility_check=can_use_messaging,
            help_text=_('Configure and schedule SMS messages and keywords'),
        ),
        Tile(
            request,
            title=_('Exchange'),
            slug='exchange',
            icon='fcc fcc-exchange',
            urlname='appstore',
            visibility_check=can_view_exchange,
            url_generator=lambda urlname, req: reverse(urlname),
            help_text=_('Download and share CommCare applications with other users around the world'),
        ),
        Tile(
            request,
            title=_('Settings'),
            slug='settings',
            icon='fcc fcc-settings',
            urlname=DefaultProjectSettingsView.urlname,
            visibility_check=is_billing_admin,
            help_text=_('Set project-wide settings and manage subscriptions'),
        ),
        Tile(
            request,
            title=_('Help Site'),
            slug='help',
            icon='fcc fcc-help',
            url='http://help.commcarehq.org/',
            help_text=_("Visit CommCare's knowledge base"),
        ),
    ]
