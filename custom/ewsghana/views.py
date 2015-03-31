import json
from django.contrib import messages
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST, require_GET
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.locations.models import SQLLocation
from custom.ewsghana.alerts.alerts import on_going_process_user, on_going_stockout_process_user, \
    urgent_non_reporting_process_user, urgent_stockout_process_user, report_reminder_process_user
from custom.ewsghana.api import GhanaEndpoint, EWSApi
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.reminders.reminders import first_soh_process_user, second_soh_process_user, \
    third_soh_process_users_and_facilities, stockout_process_user, rrirv_process_user, visit_website_process_user
from custom.ewsghana.reports.stock_levels_report import InventoryManagementData
from custom.ewsghana.tasks import ews_bootstrap_domain_task, ews_clear_stock_data_task, \
    EWS_FACILITIES
from custom.ilsgateway.views import GlobalStats
from custom.logistics.tasks import sms_users_fix, add_products_to_loc, locations_fix, sync_stock_transactions
from custom.logistics.tasks import stock_data_task
from custom.logistics.views import BaseConfigView, BaseRemindersTester
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


class RemindersTester(BaseRemindersTester):
    post_url = 'reminders_tester'

    reminders = {
        'first_soh': first_soh_process_user,
        'second_soh': second_soh_process_user,
        'third_soh': third_soh_process_users_and_facilities,
        'stockout': stockout_process_user,
        'rrirv': rrirv_process_user,
        'visit_website': visit_website_process_user,
        'alert_on_going_reporting': on_going_process_user,
        'alert_on_going_stockouts': on_going_stockout_process_user,
        'alert_urgent_non_reporting_user': urgent_non_reporting_process_user,
        'alert_urgent_stockout': urgent_stockout_process_user,
        'alert_report_reminder': report_reminder_process_user
    }

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        reminder = request.POST.get('reminder')
        phone_number = context.get('phone_number')

        if reminder and phone_number:
            phone_number = clean_phone_number(phone_number)
            v = VerifiedNumber.by_phone(phone_number, include_pending=True)
            if v and v.verified:
                user = v.owner
                if not user:
                    return self.get(request, *args, **kwargs)
                reminder_function = self.reminders.get(reminder)
                if reminder_function:
                    if reminder == 'third_soh':
                        reminder_function([user], [user.location.sql_location], test=True)
                    else:
                        reminder_function(user, test=True)
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
        ('stock_transaction', sync_stock_transactions),
    )
    config = EWSGhanaConfig.for_domain(domain)
    domain = config.domain
    endpoint = GhanaEndpoint.from_config(config)
    stock_data_task.delay(domain, endpoint, apis, config, EWS_FACILITIES)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_clear_stock_data(request, domain):
    ews_clear_stock_data_task.delay()
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_fix_sms_users(request, domain):
    config = EWSGhanaConfig.for_domain(domain)
    endpoint = GhanaEndpoint.from_config(config)
    sms_users_fix.delay(EWSApi(domain=domain, endpoint=endpoint))
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
