import json
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect
from corehq.apps.commtrack.models import CommtrackConfig, StockState
from corehq.apps.products.models import SQLProduct
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.models import SMSLog
from corehq.apps.users.models import CommCareUser, WebUser
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST
from corehq import IS_DEVELOPER
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.domain.decorators import domain_admin_required, cls_require_superuser_or_developer
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import ILSGatewayConfig, ReportRun
from custom.ilsgateway.tasks import report_run, ils_clear_stock_data_task, \
    ils_bootstrap_domain_task, get_product_stock, get_stock_transaction, get_supply_point_statuses, \
    get_delivery_group_reports, ILS_FACILITIES, LOCATION_TYPES
from custom.logistics.models import MigrationCheckpoint, StockDataCheckpoint
from casexml.apps.stock.models import StockTransaction
from custom.logistics.tasks import stock_data_task


class GlobalStats(BaseDomainView):

    section_name = 'Global Stats'
    section_url = ""
    template_name = "ilsgateway/global_stats.html"

    @property
    def main_context(self):
        contacts = CommCareUser.by_domain(self.domain, reduce=True)
        web_users = WebUser.by_domain(self.domain, reduce=True)

        main_context = super(GlobalStats, self).main_context
        context = {
            'supply_points': SQLLocation.objects.filter(domain=self.domain).count(),
            'facilities': SQLLocation.objects.filter(domain=self.domain, location_type__iexact='FACILITY').count(),
            'contacts': contacts[0]['value'] if contacts else 0,
            'web_users': web_users[0]['value'] if web_users else 0,
            'products': SQLProduct.objects.filter(domain=self.domain).count(),
            'product_stocks': StockState.objects.filter(sql_product__domain=self.domain).count(),
            'stock_transactions': StockTransaction.objects.filter(report__domain=self.domain).count(),
            'inbound_messages': SMSLog.count_incoming_by_domain(self.domain),
            'outbound_messages': SMSLog.count_outgoing_by_domain(self.domain)
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
            checkpoint = MigrationCheckpoint.objects.get(domain=self.domain)
        except MigrationCheckpoint.DoesNotExist:
            checkpoint = None

        try:
            runner = ReportRun.objects.get(domain=self.domain, complete=False)
        except ReportRun.DoesNotExist:
            runner = None

        try:
            stock_data_checkpoint = StockDataCheckpoint.objects.get(domain=self.domain)
        except StockDataCheckpoint.DoesNotExist, StockDataCheckpoint.MultipleObjectsReturned:
            stock_data_checkpoint = None

        return {
            'stock_data_checkpoint': stock_data_checkpoint,
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
    config = ILSGatewayConfig.for_domain(domain)
    domain = config.domain
    endpoint = ILSGatewayEndpoint.from_config(config)
    apis = (
        ('product_stock', get_product_stock),
        ('stock_transaction', get_stock_transaction),
        ('supply_point_status', get_supply_point_statuses),
        ('delivery_group', get_delivery_group_reports)
    )
    stock_data_task.delay(domain, endpoint, apis, LOCATION_TYPES, ILS_FACILITIES)
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
