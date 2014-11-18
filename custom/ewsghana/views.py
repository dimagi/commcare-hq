from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST
from corehq.apps.domain.decorators import domain_admin_required
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.tasks import ews_bootstrap_domain_task, ews_stock_data_task, ews_clear_stock_data_task
from custom.ilsgateway.views import GlobalStats, BaseConfigView


class GlobalStats(GlobalStats):

    template_name = "ewsghana/global_stats.html"

class EWSConfigView(BaseConfigView):
    config = EWSGhanaConfig
    urlname = 'ews_config'
    sync_urlname = 'sync_ewsghana'
    sync_stock_url = 'ews_sync_stock_data'
    clear_stock_url = 'ews_clear_stock_data'
    page_title = ugettext_noop("EWS Ghana")
    template_name = 'ilsgateway/ewsconfig.html'
    source = 'ewsghana'


@domain_admin_required
@require_POST
def sync_ewsghana(request, domain):
    ews_bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')

@domain_admin_required
@require_POST
def ews_sync_stock_data(request, domain):
    ews_stock_data_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_clear_stock_data(request, domain):
    ews_clear_stock_data_task.delay()
    return HttpResponse('OK')
