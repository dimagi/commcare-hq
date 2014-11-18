import json
from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.products.models import Product
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CommCareUser, WebUser
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST
from corehq import IS_DEVELOPER
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.domain.decorators import domain_admin_required, cls_require_superuser_or_developer
from custom.ilsgateway.models import LogisticsMigrationCheckpoint, ILSGatewayConfig, ReportRun
from custom.ilsgateway.tasks import ils_stock_data_task, report_run, ils_clear_stock_data_task, \
    ils_bootstrap_domain_task


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


class BaseConfigView(BaseCommTrackManageView):

    @cls_require_superuser_or_developer
    def dispatch(self, request, *args, **kwargs):
        return super(BaseConfigView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        try:
            checkpoint = LogisticsMigrationCheckpoint.objects.get(domain=self.domain)
        except LogisticsMigrationCheckpoint.DoesNotExist:
            checkpoint = None

        try:
            runner = ReportRun.objects.get(domain=self.domain, complete=False)
        except ReportRun.DoesNotExist:
            runner = None
        return {
            'runner': runner,
            'checkpoint': checkpoint,
            'settings': self.settings_context,
            'source': self.source,
            'sync_url': self.sync_urlname,
            'sync_stock_url': self.sync_stock_url,
            'clear_stock_url': self.clear_stock_url,
            'is_developer': IS_DEVELOPER.enabled(self.request.couch_user.username),
            'is_commtrack_enabled': CommtrackConfig.for_domain(self.domain)
        }

    @property
    def settings_context(self):
        config = self.config.for_domain(self.domain_object.name)
        if config:
            return {
                "source_config": config._doc,
            }
        else:
            return {
                "source_config": self.config()._doc
            }

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))
        config = self.config.wrap(self.settings_context['source_config'])
        config.enabled = payload['source_config'].get('enabled', None)
        config.domain = self.domain_object.name
        config.url = payload['source_config'].get('url', None)
        config.username = payload['source_config'].get('username', None)
        config.password = payload['source_config'].get('password', None)
        config.save()
        return self.get(request, *args, **kwargs)



class ILSConfigView(BaseConfigView):
    config = ILSGatewayConfig
    urlname = 'ils_config'
    sync_urlname = 'sync_ilsgateway'
    sync_stock_url = 'ils_sync_stock_data'
    clear_stock_url = 'ils_clear_stock_data'
    page_title = ugettext_noop("ILSGateway")
    template_name = 'ilsgateway/ilsconfig.html'
    source = 'ilsgateway'

@domain_admin_required
@require_POST
def sync_ilsgateway(request, domain):
    ils_bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ils_sync_stock_data(request, domain):
    ils_stock_data_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ils_clear_stock_data(request, domain):
    ils_clear_stock_data_task.delay()
    return HttpResponse('OK')

@domain_admin_required
@require_POST
def run_warehouse_runner(request, domain):
    report_run.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def end_report_run(request, domain):
    try:
        rr = ReportRun.objects.get(domain=domain, complete=False)
        rr.complete = True
        rr.save()
    except ReportRun.DoesNotExist, ReportRun.MultipleObjectsReturned:
        pass
    return HttpResponseRedirect(reverse(ILSConfigView.urlname, kwargs={'domain': domain}))
