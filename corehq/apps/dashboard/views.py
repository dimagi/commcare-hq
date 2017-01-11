from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_noop, ugettext as _
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation

from corehq import privileges, toggles
from corehq.apps.app_manager.dbaccessors import domain_has_apps, get_brief_apps_in_domain
from corehq.apps.dashboard.models import (
    TileConfiguration,
    AppsPaginatedContext,
    IconContext,
    ReportsPaginatedContext, Tile, DataPaginatedContext)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import DomainViewMixin, LoginAndDomainMixin, \
    DefaultProjectSettingsView
from corehq.apps.domain.utils import user_has_custom_top_menu
from corehq.apps.export.views import CaseExportListView, FormExportListView
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.locations.views import LocationsListView
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.users.permissions import can_view_case_exports, can_view_form_exports
from corehq.apps.users.views import DefaultProjectUserSettingsView
from corehq.apps.locations.permissions import location_safe
from corehq.apps.style.decorators import use_angular_js
from corehq.apps.cloudcare.views import FormplayerMain
from django_prbac.utils import has_privilege
from django.conf import settings


@login_and_domain_required
@location_safe
def dashboard_default(request, domain):
    return HttpResponseRedirect(default_dashboard_url(request, domain))


def default_dashboard_url(request, domain):
    couch_user = getattr(request, 'couch_user', None)

    if domain in settings.CUSTOM_DASHBOARD_PAGE_URL_NAMES:
        return reverse(settings.CUSTOM_DASHBOARD_PAGE_URL_NAMES[domain], args=[domain])

    if couch_user and not couch_user.has_permission(domain, 'access_all_locations'):
        if couch_user.is_commcare_user():
            if toggles.USE_FORMPLAYER_FRONTEND.enabled(domain):
                formplayer_view = FormplayerMain.urlname
            else:
                formplayer_view = "corehq.apps.cloudcare.views.default"
            return reverse(formplayer_view, args=[domain])
        if couch_user.has_permission(domain, 'view_reports'):
            return reverse(CaseExportListView.urlname, args=[domain])
        else:
            if can_view_case_exports(couch_user, domain):
                return reverse(CaseExportListView.urlname, args=[domain])
            elif can_view_form_exports(couch_user, domain):
                return reverse(FormExportListView.urlname, args=[domain])
        return reverse(LocationsListView.urlname, args=[domain])

    if couch_user and user_has_custom_top_menu(domain, couch_user):
        return reverse('saved_reports', args=[domain])

    if not domain_has_apps(domain):
        return reverse('default_app', args=[domain])

    return reverse(DomainDashboardView.urlname, args=[domain])


class BaseDashboardView(LoginAndDomainMixin, BasePageView, DomainViewMixin):

    @use_angular_js
    def dispatch(self, request, *args, **kwargs):
        return super(BaseDashboardView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(BaseDashboardView, self).main_context
        context.update({
            'domain': self.domain,
        })
        return context

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])


class NewUserDashboardView(BaseDashboardView):
    urlname = 'dashboard_new_user'
    page_title = ugettext_noop("HQ Dashboard")
    template_name = 'dashboard/dashboard_new_user.html'

    @property
    def page_context(self):
        return {'templates': self.templates(self.domain)}

    @classmethod
    def get_page_context(cls, domain):
        return {
            'apps': get_brief_apps_in_domain(domain),
            'templates': cls.templates(domain),
        }

    @classmethod
    def templates(cls, domain):
        templates = [{
            'heading': _('Blank Application'),
            'url': reverse('default_new_app', args=[domain]),
            'icon': 'fcc-blankapp',
            'lead': _('Start from scratch'),
            'action': 'Blank',
            'description': 'Clicked Blank App Template Tile',
        }]

        templates = [{
            'heading': _('Case Management'),
            'url': reverse('app_from_template', args=[domain, 'case_management']),
            'icon': 'fcc-casemgt',
            'lead': _('Track information over time'),
            'action': 'Case Management',
            'description': 'Clicked Case Management App Template Tile',
        }] + templates

        templates = [{
            'heading': _('Survey'),
            'url': reverse('app_from_template', args=[domain, 'survey']),
            'icon': 'fcc-survey',
            'lead': _('One-time data collection'),
            'action': 'Survey',
            'description': 'Clicked Survey App Template Tile',
        }] + templates

        return templates


class DomainDashboardView(JSONResponseMixin, BaseDashboardView):
    urlname = 'dashboard_domain'
    page_title = ugettext_noop("HQ Dashboard")
    template_name = 'dashboard/dashboard_domain.html'

    def dispatch(self, request, *args, **kwargs):
        return super(DomainDashboardView, self).dispatch(request, *args, **kwargs)

    @property
    def tile_configs(self):
        return _get_default_tile_configurations()

    @property
    def slug_to_tile(self):
        return dict([(a.slug, a) for a in self.tile_configs])

    @property
    def page_context(self):
        return {
            'dashboard_tiles': [{
                'title': d.title,
                'slug': d.slug,
                'ng_directive': d.ng_directive,
            } for d in self.tile_configs],
            'is_icds': settings.HQ_INSTANCE == 'icds',
        }

    def make_tile(self, slug, in_data):
        config = self.slug_to_tile[slug]
        return Tile(config, self.request, in_data)

    @allow_remote_invocation
    def update_tile(self, in_data):
        tile = self.make_tile(in_data['slug'], in_data)
        if not tile.is_visible:
            return {
                'success': False,
                'message': _('You do not have permission to access this tile.'),
            }
        return {
            'response': tile.context,
            'success': True,
        }

    @allow_remote_invocation
    def check_permissions(self, in_data):
        tile = self.make_tile(in_data['slug'], in_data)
        return {
            'success': True,
            'hasPermissions': tile.is_visible,
        }


def _get_default_tile_configurations():
    can_edit_data = lambda request: (request.couch_user.can_edit_data()
                                     or request.couch_user.can_access_any_exports())
    can_edit_apps = lambda request: (request.couch_user.is_web_user()
                                     or request.couch_user.can_edit_apps())
    can_view_reports = lambda request: user_can_view_reports(request.project, request.couch_user)
    can_edit_users = lambda request: (request.couch_user.can_edit_commcare_users()
                                      or request.couch_user.can_edit_web_users())

    can_view_commtrack_setup = lambda request: (request.project.commtrack_enabled)

    can_view_exchange = lambda request: can_edit_apps(request) and not settings.ENTERPRISE_MODE

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

    return [
        TileConfiguration(
            title=_('Applications'),
            slug='applications',
            icon='fcc fcc-applications',
            context_processor_class=AppsPaginatedContext,
            visibility_check=can_edit_apps,
            urlname='default_app',
            help_text=_('Build, update, and deploy applications'),
        ),
        TileConfiguration(
            title=_('Reports'),
            slug='reports',
            icon='fcc fcc-reports',
            context_processor_class=ReportsPaginatedContext,
            urlname='reports_home',
            visibility_check=can_view_reports,
            help_text=_('View worker monitoring reports and inspect '
                        'project data'),
        ),
        TileConfiguration(
            title=_('CommCare Supply Setup'),
            slug='commtrack_setup',
            icon='fcc fcc-commtrack',
            context_processor_class=IconContext,
            urlname='default_commtrack_setup',
            visibility_check=can_view_commtrack_setup,
            help_text=_("Update CommCare Supply Settings"),
        ),
        TileConfiguration(
            title=_('Data'),
            slug='data',
            icon='fcc fcc-data',
            context_processor_class=DataPaginatedContext,
            urlname="data_interfaces_default",
            visibility_check=can_edit_data,
            help_text=_('Export and manage data'),
        ),
        TileConfiguration(
            title=_('Users'),
            slug='users',
            icon='fcc fcc-users',
            context_processor_class=IconContext,
            urlname=DefaultProjectUserSettingsView.urlname,
            visibility_check=can_edit_users,
            help_text=_('Manage accounts for mobile workers '
                        'and CommCareHQ users'),
        ),
        TileConfiguration(
            title=_('Messaging'),
            slug='messaging',
            icon='fcc fcc-messaging',
            context_processor_class=IconContext,
            urlname='sms_default',
            visibility_check=can_use_messaging,
            help_text=_('Configure and schedule SMS messages and keywords'),
        ),
        TileConfiguration(
            title=_('Exchange'),
            slug='exchange',
            icon='fcc fcc-exchange',
            context_processor_class=IconContext,
            urlname='appstore',
            visibility_check=can_view_exchange,
            url_generator=lambda urlname, req: reverse(urlname),
            help_text=_('Download and share CommCare applications with '
                        'other users around the world'),
        ),
        TileConfiguration(
            title=_('Settings'),
            slug='settings',
            icon='fcc fcc-settings',
            context_processor_class=IconContext,
            urlname=DefaultProjectSettingsView.urlname,
            visibility_check=is_billing_admin,
            help_text=_('Set project-wide settings and manage subscriptions'),
        ),
        TileConfiguration(
            title=_('Help Site'),
            slug='help',
            icon='fcc fcc-help',
            context_processor_class=IconContext,
            url='http://help.commcarehq.org/',
            help_text=_("Visit CommCare's knowledge base"),
        ),
    ]
