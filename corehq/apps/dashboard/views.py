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
    DataTile,
    UsersTile,
    SettingsTile,
    MessagingTile,
    ExchangeTile,
    HelpTile,
)
from corehq.apps.domain.views import DomainViewMixin, LoginAndDomainMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.style.decorators import preview_boostrap3


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
        AppsTile,
        ReportsTile,
        DataTile,
        UsersTile,
        MessagingTile,
        ExchangeTile,
        SettingsTile,
        HelpTile,
    ]

    @property
    def slug_to_tile(self):
        return dict([(a.slug, a) for a in self.tiles])

    @property
    def page_context(self):
        return {
            'dashboard_tiles': [{
                'title': d.title,
                'slug': d.slug,
                'ng_directive': d.ng_directive,
            } for d in self.tiles],
        }

    @allow_remote_invocation
    def update_tile(self, in_data):
        tile_class = self.slug_to_tile.get(in_data.get('slug'))
        tile = tile_class(
            self.domain, self.request,
            in_data=in_data
        )
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
        tile_class = self.slug_to_tile.get(in_data.get('slug'))
        tile = tile_class(
            self.domain, self.request,
            in_data=in_data
        )
        return {
            'success': True,
            'hasPermissions': tile.is_visible,
        }
