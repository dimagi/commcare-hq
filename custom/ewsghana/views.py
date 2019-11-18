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
