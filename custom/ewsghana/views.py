from datetime import datetime
import json
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.forms.formsets import formset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST, require_GET
from django.views.generic.base import RedirectView
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.sms import process
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption, \
    set_default_consumption_for_supply_point
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
)
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.permissions import locations_access_required, user_can_edit_any_location
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.form_processor.parsers.ledgers.helpers import StockTransactionHelper
from custom.common import ALL_OPTION
from custom.ewsghana.filters import EWSDateFilter
from custom.ewsghana.forms import InputStockForm, EWSUserSettings
from custom.ewsghana.models import EWSGhanaConfig, FacilityInCharge, EWSExtension, EWSMigrationStats, \
    EWSMigrationProblem
from custom.ewsghana.tasks import set_send_to_owner_field_task
from custom.ewsghana.reports.specific_reports.dashboard_report import DashboardReport
from custom.ewsghana.reports.specific_reports.stock_status_report import StockoutsProduct, StockStatus
from custom.ewsghana.reports.stock_levels_report import InventoryManagementData, StockLevelsReport
from custom.ewsghana.tasks import balance_migration_task, migrate_email_settings
from custom.ewsghana.utils import make_url, has_input_stock_permissions, calculate_last_period
from custom.ilsgateway.views import GlobalStats
from custom.logistics.views import BaseConfigView
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.web import json_handler, json_response


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


class InputStockView(BaseDomainView):
    section_name = 'Input stock data'
    section_url = ""
    template_name = 'ewsghana/input_stock.html'

    @method_decorator(login_and_domain_required)
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

                amount = form.cleaned_data['default_consumption']
                if amount is not None:
                    set_default_consumption_for_supply_point(
                        self.domain, product.get_id, location.supply_point_id, amount
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
                StockStatus,
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
                    'default_consumption': get_default_monthly_consumption(
                        self.domain,
                        product.product_id,
                        sql_location.location_type.name,
                        sql_location.supply_point_id
                    ),
                    'units': product.units
                }
            )
        context['formset'] = InputStockFormSet(initial=initial_data)
        return context


class EWSUserExtensionView(BaseCommTrackManageView):

    template_name = 'ewsghana/user_extension.html'

    @property
    def page_context(self):
        page_context = super(EWSUserExtensionView, self).page_context
        user_id = self.kwargs['user_id']

        try:
            extension = EWSExtension.objects.get(domain=self.domain, user_id=user_id)
            sms_notifications = extension.sms_notifications
            facility = extension.location_id
        except EWSExtension.DoesNotExist:
            sms_notifications = None
            facility = None

        page_context['form'] = EWSUserSettings(user_id=user_id, domain=self.domain, initial={
            'sms_notifications': sms_notifications, 'facility': facility
        })
        page_context['couch_user'] = self.web_user
        return page_context

    @property
    def web_user(self):
        return WebUser.get(docid=self.kwargs['user_id'])

    def post(self, request, *args, **kwargs):
        form = EWSUserSettings(request.POST, user_id=kwargs['user_id'], domain=self.domain)
        if form.is_valid():
            form.save(self.web_user, self.domain)
            messages.add_message(request, messages.SUCCESS, 'Settings updated successfully!')
        return self.get(request, *args, **kwargs)


@domain_admin_required
@require_POST
def balance_email_reports_migration(request, domain):
    balance_migration_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def migrate_email_settings_view(request, domain):
    migrate_email_settings.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def fix_email_reports(request, domain):
    set_send_to_owner_field_task.delay(domain)
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


def loc_to_payload(loc):
    return {'id': loc.location_id, 'name': loc.display_name}


@locations_access_required
def non_administrative_locations_for_select2(request, domain):
    id = request.GET.get('id')
    query = request.GET.get('name', '').lower()
    if id:
        try:
            loc = SQLLocation.objects.get(location_id=id)
            if loc.domain != domain:
                raise SQLLocation.DoesNotExist()
        except SQLLocation.DoesNotExist:
            return json_response(
                {'message': 'no location with id %s found' % id},
                status_code=404,
            )
        else:
            return json_response(loc_to_payload(loc))

    locs = []
    user = request.couch_user

    user_loc = user.get_sql_location(domain)

    if user_can_edit_any_location(user, request.project):
        locs = SQLLocation.objects.filter(domain=domain, location_type__administrative=False)
    elif user_loc:
        locs = user_loc.get_descendants(include_self=True, location_type__administrative=False)

    if locs != [] and query:
        locs = locs.filter(name__icontains=query)

    return json_response(map(loc_to_payload, locs[:10]))


class BalanceMigrationView(BaseDomainView):

    template_name = 'ewsghana/balance.html'
    section_name = 'Balance'
    section_url = ''

    @property
    def page_context(self):
        return {
            'stats': get_object_or_404(EWSMigrationStats, domain=self.domain),
            'products_count': SQLProduct.objects.filter(domain=self.domain).count(),
            'locations_count': SQLLocation.objects.filter(
                domain=self.domain, location_type__administrative=True
            ).exclude(is_archived=True).count(),
            'supply_points_count': SQLLocation.objects.filter(
                domain=self.domain, location_type__administrative=False
            ).exclude(is_archived=True).count(),
            'web_users_count': WebUser.by_domain(self.domain, reduce=True)[0]['value'],
            'sms_users_count': CommCareUser.by_domain(self.domain, reduce=True)[0]['value'],
            'problems': EWSMigrationProblem.objects.filter(domain=self.domain)
        }


class BalanceEmailMigrationView(BaseDomainView):

    template_name = 'ewsghana/email_balance.html'
    section_name = 'Email Balance'
    section_url = ''

    @property
    def page_context(self):
        return {
            'problems': EWSMigrationProblem.objects.filter(domain=self.domain)
        }


class DashboardPageView(RedirectView):

    def get_redirect_url(self, *args, **kwargs):
        domain = kwargs['domain']
        url = DashboardReport.get_raw_url(domain, request=self.request)
        user = self.request.couch_user
        dm = user.get_domain_membership(domain) if user else None
        if dm:
            if dm.program_id:
                program_id = dm.program_id
            else:
                program_id = 'all'

            loc_id = ''
            if dm.location_id:
                location = SQLLocation.objects.get(location_id=dm.location_id)
                if not location.location_type.administrative:
                    url = StockStatus.get_raw_url(domain, request=self.request)
                loc_id = location.location_id
            else:
                try:
                    extension = EWSExtension.objects.get(domain=domain, user_id=user.get_id)
                    loc_id = extension.location_id
                    if loc_id:
                        url = StockStatus.get_raw_url(domain, request=self.request)
                except EWSExtension.DoesNotExist:
                    pass
            start_date, end_date = calculate_last_period()
            url = '%s?location_id=%s&filter_by_program=%s&startdate=%s&enddate=%s' % (
                url,
                loc_id or '',
                program_id if program_id else '',
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
        return url
