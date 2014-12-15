from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop, ugettext as _
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation

from corehq import toggles, privileges
from corehq.apps.app_manager.models import Application
from corehq.apps.dashboard.models import (
    TileConfiguration,
    AppsPaginatedContext,
    IconContext,
    ReportsPaginatedContext, Tile)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import DomainViewMixin, LoginAndDomainMixin, \
    DefaultProjectSettingsView
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.users.views import DefaultProjectUserSettingsView
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege


@login_and_domain_required
def dashboard_default(request, domain):
    key = [domain]
    apps = Application.get_db().view(
        'app_manager/applications_brief',
        reduce=False,
        startkey=key,
        endkey=key+[{}],
        limit=1,
    ).all()
    if len(apps) < 1:
        return HttpResponseRedirect(
            reverse(NewUserDashboardView.urlname, args=[domain]))
    return HttpResponseRedirect(
        reverse(DomainDashboardView.urlname, args=[domain]))


class BaseDashboardView(LoginAndDomainMixin, BasePageView, DomainViewMixin):

    def dispatch(self, request, *args, **kwargs):
        request.preview_bootstrap3 = True
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


class DomainDashboardView(JSONResponseMixin, BaseDashboardView):
    urlname = 'dashboard_domain'
    page_title = ugettext_noop("HQ Dashboard")
    template_name = 'dashboard/dashboard_domain.html'

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
                                     or request.couch_user.can_export_data())
    can_edit_apps = lambda request: (request.couch_user.is_web_user()
                                     or request.couch_user.can_edit_apps())
    can_view_reports = lambda request: (request.couch_user.can_view_reports()
                                        or request.couch_user.get_viewable_reports())
    can_edit_users = lambda request: (request.couch_user.can_edit_commcare_users()
                                      or request.couch_user.can_edit_web_users())

    can_view_commtrack_setup = lambda request: (request.project.commtrack_enabled)

    def _can_access_sms(request):
        try:
            ensure_request_has_privilege(request, privileges.OUTBOUND_SMS)
        except PermissionDenied:
            return False
        return True

    def _can_access_reminders(request):
        try:
            ensure_request_has_privilege(request, privileges.REMINDERS_FRAMEWORK)
            return True
        except PermissionDenied:
            return False

    can_use_messaging = lambda request: (
        (_can_access_reminders(request) or _can_access_sms(request))
        and not request.couch_user.is_commcare_user()
        and request.couch_user.can_edit_data()
    )

    is_domain_admin = lambda request: request.couch_user.is_domain_admin(request.domain)

    return [
        TileConfiguration(
            title=_('Applications'),
            slug='applications',
            icon='fcc fcc-applications',
            context_processor_class=AppsPaginatedContext,
            visibility_check=can_edit_apps,
            urlname='default_new_app',
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
            title=_('CommTrack Setup'),
            slug='commtrack_setup',
            icon='fcc fcc-commtrack',
            context_processor_class=IconContext,
            urlname='default_commtrack_setup',
            visibility_check=can_view_commtrack_setup,
            help_text=_("Update CommTrack Settings"),
        ),
        TileConfiguration(
            title=_('Data'),
            slug='data',
            icon='fcc fcc-data',
            context_processor_class=IconContext,
            urlname='data_interfaces_default',
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
            visibility_check=can_edit_apps,
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
            visibility_check=is_domain_admin,
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
