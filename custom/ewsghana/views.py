from datetime import datetime
import json
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.forms.formsets import formset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.http.response import Http404
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST, require_GET
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import StockState, StockTransactionHelper
from corehq.apps.commtrack.sms import process
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.products.models import Product
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.locations.models import SQLLocation
from custom.common import ALL_OPTION
from custom.ewsghana.alerts.alerts import on_going_process_user, on_going_stockout_process_user, \
    urgent_non_reporting_process_user, urgent_stockout_process_user, report_reminder_process_user
from custom.ewsghana.api import GhanaEndpoint, EWSApi
from custom.ewsghana.forms import InputStockForm
from custom.ewsghana.models import EWSGhanaConfig, FacilityInCharge
from custom.ewsghana.reminders.reminders import first_soh_process_user, second_soh_process_user, \
    third_soh_process_users_and_facilities, stockout_process_user, rrirv_process_user, visit_website_process_user
from custom.ewsghana.reports.specific_reports.stock_status_report import StockoutsProduct
from custom.ewsghana.reports.stock_levels_report import InventoryManagementData, StockLevelsReport
from custom.ewsghana.stock_data import EWSStockDataSynchronization
from custom.ewsghana.tasks import ews_bootstrap_domain_task, ews_clear_stock_data_task, \
    delete_last_migrated_stock_data, convert_user_data_fields_task
from custom.ewsghana.utils import make_url, has_input_stock_permissions
from custom.ilsgateway.views import GlobalStats
from custom.logistics.tasks import add_products_to_loc, locations_fix, resync_web_users
from custom.logistics.tasks import stock_data_task
from custom.logistics.views import BaseConfigView, BaseRemindersTester
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.web import json_handler


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
                        reminder_function([user], [user.sql_location], test=True)
                    else:
                        reminder_function(user, test=True)
        messages.success(request, "Reminder was sent successfully")
        return self.get(request, *args, **kwargs)


class InputStockView(BaseDomainView):
    section_name = 'Input stock data'
    section_url = ""
    template_name = 'ewsghana/input_stock.html'

    def dispatch(self, request, *args, **kwargs):
        couch_user = self.request.couch_user
        site_code = kwargs['site_code']
        try:
            sql_location = SQLLocation.objects.get(site_code=site_code, domain=self.domain)
            if not has_input_stock_permissions(couch_user, sql_location, self.domain):
                raise PermissionDenied()
        except SQLLocation.DoesNotExist:
            raise Http404()

        return super(InputStockView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        InputStockFormSet = formset_factory(InputStockForm)
        formset = InputStockFormSet(request.POST)
        if formset.is_valid():
            try:
                location = SQLLocation.objects.get(site_code=kwargs['site_code'], domain=self.domain)
            except SQLLocation.DoesNotExist:
                raise Http404()
            data = []
            for form in formset:
                product = Product.get(docid=form.cleaned_data['product_id'])
                if form.cleaned_data['receipts']:
                    data.append(
                        StockTransactionHelper(
                            domain=self.domain,
                            location_id=location.location_id,
                            case_id=location.supply_point_id,
                            product_id=product.get_id,
                            action=const.StockActions.RECEIPTS,
                            quantity=form.cleaned_data['receipts']
                        ),
                    )
                if form.cleaned_data['stock_on_hand'] is not None:
                    data.append(
                        StockTransactionHelper(
                            domain=self.domain,
                            location_id=location.location_id,
                            case_id=location.supply_point_id,
                            product_id=product.get_id,
                            action=const.StockActions.STOCKONHAND,
                            quantity=form.cleaned_data['stock_on_hand']
                        ),
                    )
            if data:
                unpacked_data = {
                    'timestamp': datetime.utcnow(),
                    'user': self.request.couch_user,
                    'phone': 'ewsghana-input-stock',
                    'location': location.couch_location,
                    'transactions': data,
                }
                process(self.domain, unpacked_data)
            url = make_url(
                StockLevelsReport,
                self.domain,
                '?location_id=%s&filter_by_program=%s&startdate='
                '&enddate=&report_type=&filter_by_product=%s',
                (location.location_id, ALL_OPTION, ALL_OPTION)
            )
            return HttpResponseRedirect(url)
        context = self.get_context_data(**kwargs)
        context['formset'] = formset
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(InputStockView, self).get_context_data(**kwargs)
        try:
            sql_location = SQLLocation.objects.get(domain=self.domain, site_code=kwargs.get('site_code'))
        except SQLLocation.DoesNotExist:
            raise Http404()
        InputStockFormSet = formset_factory(InputStockForm, extra=0)
        initial_data = []

        for product in sql_location.products.order_by('name'):
            try:
                stock_state = StockState.objects.get(
                    case_id=sql_location.supply_point_id,
                    product_id=product.product_id
                )
                stock_on_hand = stock_state.stock_on_hand
                monthly_consumption = stock_state.get_monthly_consumption()
            except StockState.DoesNotExist:
                stock_on_hand = 0
                monthly_consumption = 0
            initial_data.append(
                {
                    'product_id': product.product_id,
                    'product': product.name,
                    'stock_on_hand': int(stock_on_hand),
                    'monthly_consumption': round(monthly_consumption) if monthly_consumption else 0,
                    'units': product.units
                }
            )
        context['formset'] = InputStockFormSet(initial=initial_data)
        return context


@domain_admin_required
@require_POST
def sync_ewsghana(request, domain):
    ews_bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_sync_stock_data(request, domain):
    config = EWSGhanaConfig.for_domain(domain)
    domain = config.domain
    endpoint = GhanaEndpoint.from_config(config)
    stock_data_task.delay(EWSStockDataSynchronization(domain, endpoint))
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_clear_stock_data(request, domain):
    ews_clear_stock_data_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ews_resync_web_users(request, domain):
    config = EWSGhanaConfig.for_domain(domain)
    endpoint = GhanaEndpoint.from_config(config)
    resync_web_users.delay(EWSApi(domain=domain, endpoint=endpoint))
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


@domain_admin_required
@require_POST
def delete_last_stock_data(request, domain):
    delete_last_migrated_stock_data.delay(domain)
    return HttpResponse('OK')


def convert_user_data_fields(request, domain):
    convert_user_data_fields_task.delay(domain)
    return HttpResponse('OK')


@require_GET
def inventory_management(request, domain):

    inventory_management_ds = InventoryManagementData(
        config=dict(
            program=None, products=None, domain=domain,
            startdate=force_to_datetime(request.GET.get('startdate')),
            enddate=force_to_datetime(request.GET.get('enddate')), location_id=request.GET.get('location_id'),
            custom_date=True
        )
    )
    return HttpResponse(
        json.dumps(inventory_management_ds.charts[0].data, default=json_handler),
        content_type='application/json'
    )


@require_GET
def stockouts_product(request, domain):

    stockout_graph = StockoutsProduct(
        config=dict(
            program=None, products=None, domain=domain,
            startdate=force_to_datetime(request.GET.get('startdate')),
            enddate=force_to_datetime(request.GET.get('enddate')), location_id=request.GET.get('location_id'),
            custom_date=True
        )
    )
    return HttpResponse(
        json.dumps(stockout_graph.charts[0].data, default=json_handler),
        content_type='application/json'
    )


@require_POST
def configure_in_charge(request, domain):
    in_charge_ids = request.POST.getlist('users[]')
    location_id = request.POST.get('location_id')
    location = SQLLocation.objects.get(location_id=location_id)
    for user_id in in_charge_ids:
        FacilityInCharge.objects.get_or_create(user_id=user_id, location=location)
    FacilityInCharge.objects.filter(location=location).exclude(user_id__in=in_charge_ids).delete()
    return HttpResponse('OK')
