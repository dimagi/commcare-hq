from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop, ugettext as _
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation

from corehq import toggles
from corehq.apps.app_manager.models import Application
from corehq.apps.dashboard.models import (
    AppsTile,
    ReportsTile,
    SettingsTile,
    MessagingTile,
    ExchangeTile,
    HelpTile,
    TileConfiguration, ConfigurableIconTile, ConfigurablePaginatedTile, PaginatedTileConfiguration, MockPaginator,
    AppsPaginator)
from corehq.apps.domain.views import DomainViewMixin, LoginAndDomainMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.style.decorators import preview_boostrap3
from corehq.apps.users.views import DefaultProjectUserSettingsView


@toggles.DASHBOARD_PREVIEW.required_decorator()
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

    @method_decorator(preview_boostrap3())
    @method_decorator(toggles.DASHBOARD_PREVIEW.required_decorator())
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


class DomainDashboardView(JSONResponseMixin, BaseDashboardView):
    urlname = 'dashboard_domain'
    page_title = ugettext_noop("HQ Dashboard")
    template_name = 'dashboard/dashboard_domain.html'
    tiles = [
        # AppsTile,
        # ReportsTile,
        # DataTile,
        # UsersTile,
        # MessagingTile,
        # ExchangeTile,
        # SettingsTile,
        # HelpTile,
    ]

    def get_tile_configs(self):
        return _get_default_tile_configurations()

    @property
    def slug_to_tile(self):
        return dict([(a.slug, a) for a in self.get_tile_configs()])

    def make_tile(self, slug, in_data):
        config = self.slug_to_tile[slug]
        # todo: could clean this up or move to factory
        if config.tile_type == 'icon':
            return ConfigurableIconTile(config, self.domain, self.request, in_data)
        else:
            assert config.tile_type == 'paginate'
            assert isinstance(config, PaginatedTileConfiguration)
            return ConfigurablePaginatedTile(config, config.paginator_class, self.domain, self.request, in_data)

    @property
    def page_context(self):
        return {
            'dashboard_tiles': [{
                'title': d.title,
                'slug': d.slug,
                'ng_directive': d.ng_directive,
            } for d in self.get_tile_configs()],
        }

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
    can_edit_data = lambda request: request.couch_user.can_edit_data() or request.couch_user.can_export_data()
    can_edit_apps = lambda request: request.couch_user.is_web_user() or request.couch_user.can_edit_apps()
    USER_CONFIG = {
        'tile_type': 'icon',
        'title': _('Users'),
        'slug': 'users',
        'icon': 'dashboard-icon-users',
        'url_generator': lambda request: reverse(DefaultProjectUserSettingsView.urlname, args=[request.domain]),
        'visibility_check': lambda request: request.couch_user.can_edit_commcare_users() or request.couch_user.can_edit_web_users()
    }

    return [
        TileConfiguration(
            tile_type='icon',
            title=_('Data'),
            slug='data',
            icon='dashboard-icon-data',
            url_generator=lambda request: reverse('data_interfaces_default', args=[request.domain]),
            visibility_check=can_edit_data,
        ),
        TileConfiguration(**USER_CONFIG),
        PaginatedTileConfiguration(
            tile_type='paginate',
            title=_('Applications'),
            slug='applications',
            icon='dashboard-icon-applications',
            paginator_class=AppsPaginator,
            url_generator=lambda request: None,
            visibility_check=can_edit_apps,
        )
    ]
