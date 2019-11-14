import json
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.forms.formsets import formset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.http.response import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST, require_GET
from django.views.generic.base import RedirectView
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption, \
    set_default_consumption_for_supply_point
from corehq.apps.domain.decorators import (
    login_and_domain_required,
)
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.locations.permissions import locations_access_required, location_safe
from corehq.apps.products.models import SQLProduct
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import WebUser
from custom.common import ALL_OPTION
from custom.ewsghana.models import FacilityInCharge, EWSExtension
from custom.ewsghana.reports.specific_reports.dashboard_report import DashboardReport
from custom.ewsghana.reports.specific_reports.stock_status_report import StockoutsProduct, StockStatus
from custom.ewsghana.reports.stock_levels_report import InventoryManagementData
from custom.ewsghana.utils import make_url, has_input_stock_permissions, calculate_last_period, Msg
from custom.ilsgateway.views import GlobalStats
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.web import json_handler, json_response


@require_GET
@location_safe
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
@location_safe
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
@location_safe
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
@location_safe
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

    if user.is_domain_admin(domain):
        locs = SQLLocation.objects.filter(domain=domain, location_type__administrative=False)
    elif user_loc:
        locs = user_loc.get_descendants(include_self=True, location_type__administrative=False)

    if locs != [] and query:
        locs = locs.filter(name__icontains=query)

    return json_response(list(map(loc_to_payload, locs[:10])))


@location_safe
class DashboardPageView(RedirectView):

    def get_redirect_url(self, *args, **kwargs):
        domain = kwargs['domain']
        url = DashboardReport.get_raw_url(domain, request=self.request)
        user = self.request.couch_user if self.request.user.is_authenticated else None
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
