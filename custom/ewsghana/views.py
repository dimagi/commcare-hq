import json
import datetime
from django.contrib import messages
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST, require_GET
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.locations.models import SQLLocation
from custom.ewsghana.api import GhanaEndpoint, EWSApi
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.reminders.reminders import first_soh_process_user, second_soh_process_user, \
    third_soh_process_users_and_facilities, stockout_process_user, rrirv_process_user, visit_website_process_user
from custom.ewsghana.reports.stock_levels_report import InventoryManagementData
from custom.ewsghana.tasks import ews_bootstrap_domain_task, ews_clear_stock_data_task, \
    EWS_FACILITIES
from custom.ilsgateway.tasks import get_product_stock, get_stock_transaction
from custom.ilsgateway.views import GlobalStats, BaseConfigView
from custom.logistics.tasks import language_fix, add_products_to_loc, locations_fix
from custom.logistics.tasks import stock_data_task
from dimagi.utils.dates import force_to_datetime


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


class RemindersTester(BaseDomainView):
    section_name = 'Reminders tester'
    section_url = ""
    template_name = "ewsghana/reminders_tester.html"

    def get_context_data(self, **kwargs):
        context = super(RemindersTester, self).get_context_data(**kwargs)
        context['phone_number'] = kwargs.get('phone_number')
        return context

    @property
    def main_context(self):
        main_context = super(RemindersTester, self).main_context
        main_context.update({
            'reminders': ['first_soh', 'second_soh', 'third_soh', 'stockout', 'rrirv', 'visit_website'],
        })
        return main_context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        reminder = request.POST.get('reminder')
        phone_number = context.get('phone_number')

        if reminder and phone_number:
            phone_number = clean_phone_number(phone_number)
            v = VerifiedNumber.by_phone(phone_number, include_pending=True)
            if v and v.verified:
                user = v.owner
                if reminder == 'first_soh':
                    first_soh_process_user(user, test=True)
                elif reminder == 'second_soh':
                    now = datetime.datetime.utcnow()
                    date = now - datetime.timedelta(days=5)
                    second_soh_process_user(user, date, test=True)
                elif reminder == 'third_soh':
                    third_soh_process_users_and_facilities([user], [user.location.sql_location], test=True)
                elif reminder == 'stockout':
                    stockout_process_user(user, test=True)
                elif reminder == 'rrirv':
                    rrirv_process_user(user, test=True)
                elif reminder == 'visit_website':
                    visit_website_process_user(user, test=True)
        messages.success(request, "Reminder was sent successfully")
        return self.get(request, *args, **kwargs)


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
def ews_fix_languages(request, domain):
    config = EWSGhanaConfig.for_domain(domain)
    endpoint = GhanaEndpoint.from_config(config)
    language_fix.delay(EWSApi(domain=domain, endpoint=endpoint))
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_fix_locations(request, domain):
    locations_fix.delay(domain=domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_add_products_to_locs(request, domain):
    config = EWSGhanaConfig.for_domain(domain)
    endpoint = GhanaEndpoint.from_config(config)
    add_products_to_loc.delay(EWSApi(domain=domain, endpoint=endpoint))
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def clear_products(request, domain):
    locations = SQLLocation.objects.filter(domain=domain)
    for loc in locations:
        loc.products = []
        loc.save()
    return HttpResponse('OK')


@require_GET
def inventory_management(request, domain):

    inventory_management_ds = InventoryManagementData(
        config=dict(
            program=None, products=None, domain=domain,
            startdate=force_to_datetime(request.GET.get('startdate')),
            enddate=force_to_datetime(request.GET.get('enddate')), location_id=request.GET.get('location_id')
        )
    )
    return HttpResponse(
        json.dumps(inventory_management_ds.charts[0].data),
        mimetype='application/json'
    )
