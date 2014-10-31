import json
from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.commtrack.models import Product, CommtrackConfig
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CommCareUser, WebUser
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST
from corehq import IS_DEVELOPER
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.domain.decorators import domain_admin_required, cls_require_superuser_or_developer
from custom.ilsgateway.models import ILSMigrationCheckpoint, ILSGatewayConfig
from custom.ilsgateway.tasks import bootstrap_domain_task as ils_bootstrap_domain_task, \
    stock_data_task, report_run, clear_stock_data_task


class GlobalStats(BaseDomainView):

    section_name = 'Global Stats'
    section_url = ""
    template_name = "ilsgateway/global_stats.html"

    @property
    def main_context(self):
        try:
            facilities = Location.filter_by_type_count(self.domain, 'FACILITY')
        except TypeError:
            facilities = 0

        contacts = CommCareUser.by_domain(self.domain, reduce=True)
        web_users = WebUser.by_domain(self.domain, reduce=True)

        try:
            products = len(Product.by_domain(self.domain))
        except ResourceNotFound:
            products = 0

        main_context = super(GlobalStats, self).main_context
        context = {
            'supply_points': len(list(Location.by_domain(self.domain))),
            'facilities': facilities,
            'contacts': contacts[0]['value'] if contacts else 0,
            'web_users': web_users[0]['value'] if web_users else 0,
            'products': products,
            # TODO add next after the enlargement ILS migration
            'product_stocks': 0,
            'stock_transactions': 0,
            'inbound_messages': 0,
            'outbound_messages': 0
        }
        main_context.update(context)
        return main_context


class ILSConfigView(BaseCommTrackManageView):
    urlname = 'ils_config'
    sync_urlname = 'sync_ilsgateway'
    page_title = ugettext_noop("ILSGateway")
    template_name = 'ilsgateway/ilsconfig.html'
    source = 'ilsgateway'

    @cls_require_superuser_or_developer
    def dispatch(self, request, *args, **kwargs):
        return super(ILSConfigView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        try:
            checkpoint = ILSMigrationCheckpoint.objects.get(domain=self.domain)
        except ILSMigrationCheckpoint.DoesNotExist:
            checkpoint = None
        return {
            'checkpoint': checkpoint,
            'settings': self.settings_context,
            'source': self.source,
            'sync_url': self.sync_urlname,
            'is_developer': IS_DEVELOPER.enabled(self.request.couch_user.username),
            'is_commtrack_enabled': CommtrackConfig.for_domain(self.domain)
        }

    @property
    def settings_context(self):
        config = ILSGatewayConfig.for_domain(self.domain_object.name)

        if config:
            return {
                "source_config": config._doc,
            }
        else:
            return {
                "source_config": ILSGatewayConfig()._doc
            }

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))
        ils = ILSGatewayConfig.wrap(self.settings_context['source_config'])
        ils.enabled = payload['source_config'].get('enabled', None)
        ils.domain = self.domain_object.name
        ils.url = payload['source_config'].get('url', None)
        ils.username = payload['source_config'].get('username', None)
        ils.password = payload['source_config'].get('password', None)
        ils.save()
        return self.get(request, *args, **kwargs)


@domain_admin_required
@require_POST
def sync_ilsgateway(request, domain):
    ils_bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def sync_stock_data(request, domain):
    stock_data_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def clear_stock_data(request, domain):
    clear_stock_data_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def run_warehouse_runner(request, domain):
    report_run.delay(domain)
    return HttpResponse('OK')
