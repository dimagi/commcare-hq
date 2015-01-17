from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST
from corehq.apps.domain.decorators import domain_admin_required
from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.tasks import ews_bootstrap_domain_task, ews_clear_stock_data_task, \
    EWS_FACILITIES
from custom.ilsgateway.tasks import get_product_stock, get_stock_transaction
from custom.ilsgateway.views import GlobalStats, BaseConfigView
from custom.logistics.tasks import stock_data_task
from custom.logistics.tasks import resync_webusers_passwords_task


class EWSGlobalStats(GlobalStats):
    template_name = "ewsghana/global_stats.html"
    show_supply_point_types = True
    root_name = 'Country'


class EWSConfigView(BaseConfigView):
    config = EWSGhanaConfig
    urlname = 'ews_config'
    sync_urlname = 'sync_ewsghana'
    sync_stock_url = 'ews_sync_stock_data'
    clear_stock_url = 'ews_clear_stock_data'
    page_title = ugettext_noop("EWS Ghana")
    template_name = 'ewsghana/ewsconfig.html'
    source = 'ewsghana'


@domain_admin_required
@require_POST
def sync_ewsghana(request, domain):
    ews_bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_sync_stock_data(request, domain):
    apis = (
        ('product_stock', get_product_stock),
        ('stock_transaction', get_stock_transaction)
    )
    config = EWSGhanaConfig.for_domain(domain)
    domain = config.domain
    endpoint = GhanaEndpoint.from_config(config)
    stock_data_task.delay(domain, endpoint, apis, EWS_FACILITIES)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_clear_stock_data(request, domain):
    ews_clear_stock_data_task.delay()
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_resync_passwords(request, domain):
    config = EWSGhanaConfig.for_domain(domain)
    endpoint = GhanaEndpoint.from_config(config)
    resync_webusers_passwords_task.delay(config, endpoint)
    return HttpResponse('OK')
