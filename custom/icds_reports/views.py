from collections import OrderedDict
from datetime import date, datetime
from wsgiref.util import FileWrapper

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models.query_utils import Q
from django.http.response import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.generic.base import RedirectView, TemplateView, View

import requests
from celery.result import AsyncResult
from dateutil.relativedelta import relativedelta

from couchexport.export import Format
from couchexport.shortcuts import export_response

from custom.icds_reports.utils.topojson_util.topojson_util import get_block_topojson_for_state, get_map_name
from dimagi.utils.dates import add_months, force_to_date

from corehq import toggles
from corehq.apps.domain.decorators import api_auth, login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.hqwebapp.views import BugReportView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import (
    location_safe,
    user_can_access_location_id
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions, UserRole
from corehq.blobs.exceptions import NotFound
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.toggles import ICDS_DASHBOARD_TEMPORARY_DOWNTIME
from corehq.util.files import safe_filename_header
from corehq.util.view_utils import reverse
from custom.icds.const import AWC_LOCATION_TYPE_CODE
from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import (
    AWC_INFRASTRUCTURE_EXPORT,
    AWW_INCENTIVE_REPORT,
    BHD_ROLE,
    CHILDREN_EXPORT,
    DASHBOARD_USAGE_EXPORT,
    DEMOGRAPHICS_EXPORT,
    GROWTH_MONITORING_LIST_EXPORT,
    INDIA_TIMEZONE,
    ISSNIP_MONTHLY_REGISTER_PDF,
    LS_REPORT_EXPORT,
    PREGNANT_WOMEN_EXPORT,
    SYSTEM_USAGE_EXPORT,
    THR_REPORT_EXPORT,
    AggregationLevels,
    LocationTypes,
    CAS_API_PAGE_SIZE,
    SERVICE_DELIVERY_REPORT,
    CHILD_GROWTH_TRACKER_REPORT,
    POSHAN_PROGRESS_REPORT,
    AWW_ACTIVITY_REPORT
)
from custom.icds_reports.dashboard_utils import get_dashboard_template_context
from custom.icds_reports.models.aggregate import AwcLocation
from custom.icds_reports.models.helper import IcdsFile
from custom.icds_reports.models.views import AggAwcDailyView, NICIndicatorsView
from custom.icds_reports.permissions import can_access_location_data
from custom.icds_reports.queries import get_cas_data_blob_file
from custom.icds_reports.reports.adhaar import (
    get_adhaar_data_chart,
    get_adhaar_data_map,
    get_adhaar_sector_data,
)
from custom.icds_reports.reports.adolescent_girls import (
    get_adolescent_girls_data_chart,
    get_adolescent_girls_data_map,
    get_adolescent_girls_sector_data,
)
from custom.icds_reports.reports.adult_weight_scale import (
    get_adult_weight_scale_data_chart,
    get_adult_weight_scale_data_map,
    get_adult_weight_scale_sector_data,
)
from custom.icds_reports.reports.awc_daily_status import (
    get_awc_daily_status_data_chart,
    get_awc_daily_status_data_map,
    get_awc_daily_status_sector_data,
)
from custom.icds_reports.reports.awc_reports import (
    get_awc_report_beneficiary,
    get_awc_report_demographics,
    get_awc_report_infrastructure,
    get_awc_report_lactating,
    get_awc_report_pregnant,
    get_awc_reports_maternal_child,
    get_awc_reports_pse,
    get_awc_reports_system_usage,
    get_beneficiary_details,
    get_pregnant_details,
)
from custom.icds_reports.reports.children_initiated_data import (
    get_children_initiated_data_chart,
    get_children_initiated_data_map,
    get_children_initiated_sector_data,
)
from custom.icds_reports.reports.clean_water import (
    get_clean_water_data_chart,
    get_clean_water_data_map,
    get_clean_water_sector_data,
)
from custom.icds_reports.reports.daily_indicators import get_daily_indicators
from custom.icds_reports.reports.disha import DishaDump
from custom.icds_reports.reports.early_initiation_breastfeeding import (
    get_early_initiation_breastfeeding_chart,
    get_early_initiation_breastfeeding_data,
    get_early_initiation_breastfeeding_map,
)
from custom.icds_reports.reports.enrolled_children import (
    get_enrolled_children_data_chart,
    get_enrolled_children_data_map,
    get_enrolled_children_sector_data,
)
from custom.icds_reports.reports.enrolled_women import (
    get_enrolled_women_data_chart,
    get_enrolled_women_data_map,
    get_enrolled_women_sector_data,
)
from custom.icds_reports.reports.exclusive_breastfeeding import (
    get_exclusive_breastfeeding_data_chart,
    get_exclusive_breastfeeding_data_map,
    get_exclusive_breastfeeding_sector_data,
)
from custom.icds_reports.reports.fact_sheets import FactSheetsReport
from custom.icds_reports.reports.functional_toilet import (
    get_functional_toilet_data_chart,
    get_functional_toilet_data_map,
    get_functional_toilet_sector_data,
)
from custom.icds_reports.reports.immunization_coverage_data import (
    get_immunization_coverage_data_chart,
    get_immunization_coverage_data_map,
    get_immunization_coverage_sector_data,
)
from custom.icds_reports.reports.infantometer import (
    get_infantometer_data_chart,
    get_infantometer_data_map,
    get_infantometer_sector_data,
)
from custom.icds_reports.reports.infants_weight_scale import (
    get_infants_weight_scale_data_chart,
    get_infants_weight_scale_data_map,
    get_infants_weight_scale_sector_data,
)
from custom.icds_reports.reports.institutional_deliveries_sector import (
    get_institutional_deliveries_data_chart,
    get_institutional_deliveries_data_map,
    get_institutional_deliveries_sector_data,
)
from custom.icds_reports.reports.lactating_enrolled_women import (
    get_lactating_enrolled_data_chart,
    get_lactating_enrolled_women_data_map,
    get_lactating_enrolled_women_sector_data,
)
from custom.icds_reports.reports.lady_supervisor import (
    get_lady_supervisor_data,
)
from custom.icds_reports.reports.medicine_kit import (
    get_medicine_kit_data_chart,
    get_medicine_kit_data_map,
    get_medicine_kit_sector_data,
)
from custom.icds_reports.reports.mwcd_indicators import (
    get_mwcd_indicator_api_data,
)
from custom.icds_reports.reports.new_born_with_low_weight import (
    get_newborn_with_low_birth_weight_chart,
    get_newborn_with_low_birth_weight_data,
    get_newborn_with_low_birth_weight_map,
)
from custom.icds_reports.reports.prevalence_of_severe import (
    get_prevalence_of_severe_data_chart,
    get_prevalence_of_severe_data_map,
    get_prevalence_of_severe_sector_data,
)
from custom.icds_reports.reports.prevalence_of_stunting import (
    get_prevalence_of_stunting_data_chart,
    get_prevalence_of_stunting_data_map,
    get_prevalence_of_stunting_sector_data,
)
from custom.icds_reports.reports.prevalence_of_undernutrition import (
    get_prevalence_of_undernutrition_data_chart,
    get_prevalence_of_undernutrition_data_map,
    get_prevalence_of_undernutrition_sector_data,
)
from custom.icds_reports.reports.registered_household import (
    get_registered_household_data_chart,
    get_registered_household_data_map,
    get_registered_household_sector_data,
)
from custom.icds_reports.reports.service_delivery_dashboard import (
    get_service_delivery_data,
)
from custom.icds_reports.reports.service_delivery_dashboard_data import (
    get_service_delivery_report_data,
    get_service_delivery_details,
)
from custom.icds_reports.reports.stadiometer import (
    get_stadiometer_data_chart,
    get_stadiometer_data_map,
    get_stadiometer_sector_data,
)
from custom.icds_reports.tasks import (
    move_ucr_data_into_aggregation_tables,
    prepare_excel_reports,
    prepare_issnip_monthly_register_reports,
)
from custom.icds_reports.utils import (
    current_month_stunting_column,
    current_month_wasting_column,
    get_age_filter,
    get_age_filter_in_months,
    get_datatables_ordering_info,
    get_location_filter,
    get_location_level,
    icds_pre_release_features,
    india_now,
    filter_cas_data_export,
    get_deprecation_info,
    get_location_replacement_name,
    timestamp_string_to_date_string,
    datetime_to_date_string
)
from custom.icds_reports.utils.data_accessor import (
    get_awc_covered_data_with_retrying,
    get_inc_indicator_api_data,
    get_program_summary_data_with_retrying,
)

from custom.icds_reports.reports.governance_apis import (
    get_home_visit_data,
    get_vhnd_data,
    get_beneficiary_data,
    get_state_names,
    get_cbe_data)

from custom.icds_reports.reports.bihar_api import get_api_demographics_data, get_mother_details,\
    get_api_vaccine_data, get_api_ag_school_data

from . import const
from .exceptions import InvalidLocationTypeException, TableauTokenException

# checks required to view the dashboard
from custom.icds_reports.reports.poshan_progress_dashboard_data import get_poshan_progress_dashboard_data

DASHBOARD_CHECKS = [
    toggles.DASHBOARD_ICDS_REPORT.required_decorator(),
    require_permission(Permissions.view_report, 'custom.icds_reports.reports.reports.DashboardReport',
                       login_decorator=None),
    login_and_domain_required,
    can_access_location_data
]

DASHBOARD_CHECKS_FOR_TEMPLATE = DASHBOARD_CHECKS[:-1]


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class LegacyTableauRedirectView(RedirectView):

    permanent = True
    pattern_name = 'icds_dashboard'

    def get_redirect_url(self, domain=None, **kwargs):
        return reverse('icds_dashboard', args=[domain])


def _get_user_location(user, domain):
    '''
    Takes a couch_user and returns that users parentage and the location id
    '''
    try:
        user_location_id = user.get_domain_membership(domain).location_id
        loc = SQLLocation.by_location_id(user_location_id)
        location_type_code = loc.location_type.code

        # Assuming no web users below block level
        state_id = 'All'
        district_id = 'All'
        block_id = 'All'
        if location_type_code == 'state':
            state_id = loc.location_id
        elif location_type_code == 'district':
            state_id = loc.parent.location_id
            district_id = loc.location_id
        elif location_type_code == 'block':
            state_id = loc.parent.parent.location_id
            district_id = loc.parent.location_id
            block_id = loc.location_id

    except Exception:
        location_type_code = 'national'
        user_location_id = ''
        state_id = 'All'
        district_id = 'All'
        block_id = 'All'
    return location_type_code, user_location_id, state_id, district_id, block_id


def get_tableau_trusted_url(client_ip):
    """
    Generate a login-free URL to access Tableau views for the client with IP client_ip
    See Tableau Trusted Authentication https://onlinehelp.tableau.com/current/server/en-us/trusted_auth.htm
    """
    access_token = get_tableau_access_token(const.TABLEAU_USERNAME, client_ip)
    url = "{tableau_trusted}{access_token}/#/views/".format(
        tableau_trusted=const.TABLEAU_TICKET_URL,
        access_token=access_token
    )
    return url


def get_tableau_access_token(tableau_user, client_ip):
    """
    Request an access_token from Tableau
    Note: the IP address of the webworker that this code runs on should be configured to request tokens in Tableau

    args:
        tableau_user: username of a valid tableau_user who can access the Tableau views
        client_ip: IP address of the client who should redee be allowed to redeem the Tableau trusted token
                   if this is empty, the token returned can be redeemed on any IP address
    """
    r = requests.post(
        const.TABLEAU_TICKET_URL,
        data={'username': tableau_user, 'client_ip': client_ip},
        verify=False
    )

    if r.status_code == 200:
        if r.text == const.TABLEAU_INVALID_TOKEN:
            raise TableauTokenException("Tableau server failed to issue a valid token")
        else:
            return r.text
    else:
        raise TableauTokenException("Token request failed with code {}".format(r.status_code))


@location_safe
@method_decorator(DASHBOARD_CHECKS_FOR_TEMPLATE, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'icds_reports/dashboard.html'
    downtime_template_name = 'icds_reports/dashboard_down.html'

    def get_template_names(self):
        return [self.template_name] if not self.show_downtime else [self.downtime_template_name]

    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def show_downtime(self):
        return (
            ICDS_DASHBOARD_TEMPORARY_DOWNTIME.enabled(self.domain)
            and not self.request.GET.get('bypass-downtime')
        )

    @property
    def couch_user(self):
        return self.request.couch_user

    def get_context_data(self, **kwargs):
        kwargs.update(self.kwargs)
        kwargs.update(get_dashboard_template_context(self.domain, self.couch_user))
        kwargs['is_mobile'] = False
        return super().get_context_data(**kwargs)


@location_safe
@method_decorator(DASHBOARD_CHECKS_FOR_TEMPLATE, name='dispatch')
class MobileDashboardDownloadView(TemplateView):
    template_name = 'icds_reports/mobile_dashboard_download.html'


@location_safe
class IcdsDynamicTemplateViewBase(TemplateView):
    template_directory = None

    def get_template_names(self):
        return [f'{self.template_directory}/%s.html' % self.kwargs['template']]


class IcdsDynamicTemplateView(IcdsDynamicTemplateViewBase):
    template_directory = 'icds_reports/icds_app'


class IcdsDynamicMobileTemplateView(IcdsDynamicTemplateViewBase):
    template_directory = 'icds_reports/icds_app/mobile'


@location_safe
class BaseReportView(View):
    def get_settings(self, request, *args, **kwargs):
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))

        if (now.day == 1 or now.day == 2) and now.month == month and now.year == year:
            prev_month = now - relativedelta(months=1)
            month = prev_month.month
            year = prev_month.year

        include_test = request.GET.get('include_test', False)
        domain = self.kwargs['domain']
        current_month = datetime(year, month, 1)
        prev_month = current_month - relativedelta(months=1)
        location = request.GET.get('location_id')
        if location == 'null' or location == 'undefined':
            location = None
        selected_month = current_month

        return step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month


@location_safe
class BaseCasAPIView(View):

    def get_valid_query_month(self, month, year):
        error_message = None
        try:
            int_month = int(month)
            int_year = int(year)
            valid_query_month = date(int_year, int_month, 1)
        except (ValueError, TypeError):
            valid_query_month = None
            error_message = "Please specify valid month and year"

        return valid_query_month, error_message

    def has_access(self, location_id, user):
        if user.has_permission(self.kwargs['domain'], 'access_all_locations'):
            return True
        if location_id and user_can_access_location_id(self.kwargs['domain'], user, location_id):
            return True
        return False

    def query_month_in_range(self, query_month, start_month):
        in_range = True
        today = date.today()
        current_month = today - relativedelta(months=1) if today.day <= 2 else today
        if query_month > current_month or query_month < start_month:
            in_range = False
        return in_range

    def get_state_id_from_state_name(self, state_name):
        return SQLLocation.objects.get(name=state_name, location_type__name='state').location_id


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class ProgramSummaryView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(current_month.timetuple())[:3],
            'prev_month': tuple(prev_month.timetuple())[:3],
            'aggregation_level': 1
        }

        config.update(get_location_filter(location, domain))
        now = tuple(now.date().timetuple())[:3]
        pre_release_features = icds_pre_release_features(self.request.couch_user)
        data = get_program_summary_data_with_retrying(
            step, domain, config, now, include_test, pre_release_features
        )
        return JsonResponse(data=data)


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class TopoJsonView(BaseReportView):

    def get(self, request, *args, **kwargs):
        state = request.GET.get('state')
        topojson = get_block_topojson_for_state(state)
        data = {'topojson': topojson}
        return JsonResponse(data=data)


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class LadySupervisorView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(current_month.timetuple())[:3]
        }

        config.update(get_location_filter(location, domain))
        config['aggregation_level'] = 4

        data = get_lady_supervisor_data(
            domain, config, include_test
        )
        return JsonResponse(data=data)


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class ServiceDeliveryDashboardView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        location_filters = get_location_filter(location, domain)
        location_filters['aggregation_level'] = location_filters.get('aggregation_level', 1)

        start, length, order_by_number_column, order_by_name_column, order_dir = \
            get_datatables_ordering_info(request)
        reversed_order = True if order_dir == 'desc' else False
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        if icds_features_flag:
            data = get_service_delivery_report_data(
                domain,
                start,
                length,
                order_by_name_column,
                reversed_order,
                location_filters,
                year,
                month,
                step,
                include_test
            )
        else:
            data = get_service_delivery_data(
                domain,
                start,
                length,
                order_by_name_column,
                reversed_order,
                location_filters,
                year,
                month,
                step,
                include_test
            )
        return JsonResponse(data=data)


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class ServiceDeliveryDashboardDetailsView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        location_filters = get_location_filter(location, domain)
        location_filters['aggregation_level'] = location_filters.get('aggregation_level', 1)

        start, length, order_by_number_column, order_by_name_column, order_dir = \
            get_datatables_ordering_info(request)
        reversed_order = True if order_dir == 'desc' else False
        data = get_service_delivery_details(
            domain,
            start,
            length,
            order_by_name_column,
            reversed_order,
            location_filters,
            year,
            month,
            step,
            include_test
        )
        return JsonResponse(data=data)


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class PrevalenceOfUndernutritionView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_undernutrition_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_prevalence_of_undernutrition_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_prevalence_of_undernutrition_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_prevalence_of_undernutrition_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class LocationView(View):

    def get(self, request, *args, **kwargs):
        location_id = request.GET.get('location_id')
        user_locations_with_parents = SQLLocation.objects.get_queryset_ancestors(
            self.request.couch_user.get_sql_locations(self.kwargs['domain']), include_self=True
        ).distinct()
        parent_ids = [loc.location_id for loc in user_locations_with_parents]
        if location_id == 'null' or location_id == 'undefined':
            location_id = None
        if location_id:
            if not user_can_access_location_id(
                self.kwargs['domain'], request.couch_user, location_id
            ) and location_id not in parent_ids:
                return JsonResponse({})
            location = get_object_or_404(
                SQLLocation,
                domain=self.kwargs['domain'],
                location_id=location_id
            )
            location_list, replacement_names = get_deprecation_info([location], True)
            return JsonResponse({
                'name': location.name,
                'map_location_name': get_map_name(location),
                'location_type': location.location_type.code,
                'location_type_name': location.location_type_name,
                'user_have_access': user_can_access_location_id(
                    self.kwargs['domain'],
                    request.couch_user, location.location_id
                ),
                'user_have_access_to_parent': location.location_id in parent_ids,
                'parent_name': location.parent.name if location.parent else None,
                'parent_map_name': get_map_name(location.parent),
                'deprecates': get_location_replacement_name(location, 'deprecates', replacement_names),
                'archived_on': datetime_to_date_string(location.archived_on),
                'deprecated_to': get_location_replacement_name(location, 'deprecated_to', replacement_names),
                'deprecates_at': timestamp_string_to_date_string(location.metadata.get('deprecates_at')),
            })

        parent_id = request.GET.get('parent_id')
        name = request.GET.get('name')

        show_test = request.GET.get('include_test', False)

        locations = SQLLocation.objects.accessible_to_user(self.kwargs['domain'], self.request.couch_user).select_related('location_type')
        if not parent_id:
            locations = locations.filter(parent_id__isnull=True)
        else:
            locations = locations.filter(parent__location_id=parent_id)

        if locations.count() == 0:
            locations = user_locations_with_parents.filter(parent__location_id=parent_id)

        if name:
            locations = locations.filter(name__iexact=name)

        locations = locations.order_by('name')

        if not locations:
            return JsonResponse(data={'locations': []})

        locations_list, replacement_names = get_deprecation_info(locations, show_test)
        return JsonResponse(data={
            'locations': [
                {
                    'location_id': loc.location_id,
                    'name': loc.name,
                    'parent_id': parent_id,
                    'location_type_name': loc.location_type_name,
                    'user_have_access': user_can_access_location_id(
                        self.kwargs['domain'],
                        request.couch_user, loc.location_id
                    ),
                    'user_have_access_to_parent': loc.location_id in parent_ids,
                    'deprecates': get_location_replacement_name(loc, 'deprecates', replacement_names),
                    'archived_on': datetime_to_date_string(loc.archived_on),
                    'deprecated_to': get_location_replacement_name(loc, 'deprecated_to', replacement_names),
                    'deprecates_at': timestamp_string_to_date_string(loc.metadata.get('deprecates_at')),
                }
                for loc in locations_list
            ]
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class LocationAncestorsView(View):
    def get(self, request, *args, **kwargs):
        location_id = request.GET.get('location_id')
        if location_id == 'null' or location_id == 'undefined':
            location_id = None
        show_test = request.GET.get('include_test', False)
        selected_location = get_object_or_404(SQLLocation, location_id=location_id, domain=self.kwargs['domain'])
        parents = list(SQLLocation.objects.get_queryset_ancestors(
            self.request.couch_user.get_sql_locations(self.kwargs['domain']), include_self=True
        ).distinct()) + list(selected_location.get_ancestors())
        parent_ids = [x.pk for x in parents]
        parent_locations_ids = [loc.location_id for loc in parents]
        locations = SQLLocation.objects.accessible_to_user(
            domain=self.kwargs['domain'], user=self.request.couch_user
        ).filter(
            ~Q(pk__in=parent_ids) & (Q(parent_id__in=parent_ids) | Q(parent_id__isnull=True))
        ).select_related('parent').distinct().order_by('name')
        all_locations = list(OrderedDict.fromkeys(list(locations) + list(parents)))
        location_list, replacement_names = get_deprecation_info(all_locations, show_test, True)
        return JsonResponse(data={
            'locations': [
                {
                    'location_id': location.location_id,
                    'name': location.name,
                    'parent_id': location.parent.location_id if location.parent else None,
                    'location_type_name': location.location_type_name,
                    'user_have_access': user_can_access_location_id(
                        self.kwargs['domain'],
                        request.couch_user, location.location_id
                    ),
                    'user_have_access_to_parent': location.location_id in parent_locations_ids,
                    'deprecates': get_location_replacement_name(location, 'deprecates', replacement_names),
                    'archived_on': datetime_to_date_string(location.archived_on),
                    'deprecated_to': get_location_replacement_name(location, 'deprecated_to', replacement_names),
                    'deprecates_at': timestamp_string_to_date_string(location.metadata.get('deprecates_at')),
                }
                for location in location_list
            ],
            'selected_location': {
                'location_type_name': selected_location.location_type_name,
                'location_id': selected_location.location_id,
                'name': selected_location.name,
                'parent_id': selected_location.parent.location_id if selected_location.parent else None,
                'user_have_access': user_can_access_location_id(
                    self.kwargs['domain'],
                    request.couch_user, selected_location.location_id
                ),
                'user_have_access_to_parent': selected_location.location_id in parent_locations_ids,
                'deprecates': get_location_replacement_name(selected_location, 'deprecates', replacement_names),
                'archived_on': datetime_to_date_string(selected_location.archived_on),
                'deprecated_to': get_location_replacement_name(selected_location, 'deprecated_to', replacement_names),
                'deprecates_at': timestamp_string_to_date_string(selected_location.metadata.get('deprecates_at')),
            }
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class AWCLocationView(View):
    def get(self, request, *args, **kwargs):
        location_id = request.GET.get('location_id')
        if location_id == 'null' or location_id == 'undefined':
            location_id = None
        selected_location = get_object_or_404(SQLLocation, location_id=location_id, domain=self.kwargs['domain'])
        awcs = SQLLocation.objects.accessible_to_user(
            domain=self.kwargs['domain'], user=self.request.couch_user
        ).filter(parent_id=selected_location.pk).order_by('name')
        return JsonResponse(data={
            'locations': [
                {
                    'location_id': location.location_id,
                    'name': location.name,
                }
                for location in awcs
            ]
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class HaveAccessToLocation(View):
    def get(self, request, *args, **kwargs):
        location_id = request.GET.get('location_id')
        have_access = user_can_access_location_id(
            self.kwargs['domain'],
            request.couch_user, location_id
        )
        return JsonResponse(data={
            'haveAccess': have_access
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class AwcReportsView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        two_before = current_month - relativedelta(months=2)
        location = request.GET.get('location_id')
        if location == 'null' or location == 'undefined':
            location = None
        aggregation_level = 5

        config = {
            'aggregation_level': aggregation_level
        }
        if location:
            try:
                sql_location = SQLLocation.objects.get(location_id=location, domain=self.kwargs['domain'])
                locations = sql_location.get_ancestors(include_self=True)
                for loc in locations:
                    location_key = '%s_id' % loc.location_type.code
                    config.update({
                        location_key: loc.location_id,
                    })
            except SQLLocation.DoesNotExist:
                pass

        data = {}
        if step == 'system_usage':
            data = get_awc_reports_system_usage(
                domain,
                config,
                tuple(current_month.timetuple())[:3],
                tuple(prev_month.timetuple())[:3],
                tuple(two_before.timetuple())[:3],
                'aggregation_level',
                include_test
            )
        elif step == 'pse':
            data = get_awc_reports_pse(
                config,
                tuple(current_month.timetuple())[:3],
                self.kwargs.get('domain'),
                include_test
            )
        elif step == 'maternal_child':
            data = get_awc_reports_maternal_child(
                domain,
                config,
                tuple(current_month.timetuple())[:3],
                tuple(prev_month.timetuple())[:3],
                include_test,
                icds_pre_release_features(self.request.couch_user)
            )
        elif step == 'demographics':
            data = get_awc_report_demographics(
                domain,
                config,
                tuple(now.date().timetuple())[:3],
                tuple(current_month.timetuple())[:3],
                include_test,
                beta=icds_pre_release_features(request.couch_user)
            )
        elif step == 'awc_infrastructure':
            data = get_awc_report_infrastructure(
                domain,
                config,
                tuple(current_month.timetuple())[:3],
                include_test,
                beta=icds_pre_release_features(request.couch_user)
            )
        elif step == 'beneficiary':
            if 'awc_id' in config:
                filters = {
                    'awc_id': config['awc_id'],
                }
                age = self.request.GET.get('age', None)
                if age:
                    filters.update(get_age_filter_in_months(age))
                draw = int(request.GET.get('draw', 0))
                icds_features_flag = icds_pre_release_features(self.request.couch_user)
                start, length, order_by_number_column, order_by_name_column, order_dir = \
                    get_datatables_ordering_info(request)
                order_by_name_column = order_by_name_column or 'person_name'
                if order_by_name_column == 'age':  # age and date of birth is stored in database as one value
                    order_by_name_column = 'dob'
                elif order_by_name_column == 'current_month_nutrition_status':
                    order_by_name_column = 'current_month_nutrition_status_sort'
                elif order_by_name_column == 'current_month_stunting':
                    order_by_name_column = '{}_sort'.format(current_month_stunting_column(icds_features_flag))
                elif order_by_name_column == 'current_month_wasting':
                    order_by_name_column = '{}_sort'.format(current_month_wasting_column(icds_features_flag))
                order = "%s%s" % ('-' if order_dir == 'desc' else '', order_by_name_column)

                data = get_awc_report_beneficiary(
                    start,
                    length,
                    draw,
                    order,
                    filters,
                    tuple(current_month.timetuple())[:3],
                    tuple(two_before.timetuple())[:3],
                    icds_features_flag
                )
        elif step == 'beneficiary_details':
            data = get_beneficiary_details(
                self.request.GET.get('case_id'),
                config['awc_id'],
                tuple(current_month.timetuple())[:3]
            )
        elif step == 'pregnant':
            if 'awc_id' in config:
                icds_features_flag = icds_pre_release_features(self.request.couch_user)
                start, length, order_by_number_column, order_by_name_column, order_dir = \
                    get_datatables_ordering_info(request)
                order_by_name_column = order_by_name_column or 'person_name'
                reversed_order = True if order_dir == 'desc' else False

                data = get_awc_report_pregnant(
                    start,
                    length,
                    order_by_name_column,
                    reversed_order,
                    config['awc_id']
                )
        elif step == 'pregnant_details':
            data = get_pregnant_details(
                self.request.GET.get('case_id'),
                config['awc_id'],
            )
        elif step == 'lactating':
            if 'awc_id' in config:
                icds_features_flag = icds_pre_release_features(self.request.couch_user)
                start, length, order_by_number_column, order_by_name_column, order_dir = \
                    get_datatables_ordering_info(request)
                order_by_name_column = order_by_name_column or 'person_name'
                reversed_order = True if order_dir == 'desc' else False

                data = get_awc_report_lactating(
                    start,
                    length,
                    order_by_name_column,
                    reversed_order,
                    config['awc_id']
                )
        return JsonResponse(data=data)


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class ExportIndicatorView(View):
    def post(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        export_format = request.POST.get('format')
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        aggregation_level = int(request.POST.get('aggregation_level'))
        indicator = int(request.POST.get('indicator'))

        config = {
            'aggregation_level': aggregation_level,
            'domain': self.kwargs['domain']
        }
        beneficiary_config = {'domain': self.kwargs['domain'], 'filters': request.POST.getlist('filter[]')}

        if month and year:
            beneficiary_config['month'] = date(year, month, 1)
            config.update({
                'month': date(year, month, 1),
            })

        location = request.POST.get('location', '')

        if not location and not request.couch_user.has_permission(
                self.kwargs['domain'], 'access_all_locations'
        ):
            return HttpResponse(status_code=403)
        if location and not user_can_access_location_id(
                self.kwargs['domain'], request.couch_user, location
        ):
            return HttpResponse(status_code=403)

        sql_location = None

        if location and indicator != ISSNIP_MONTHLY_REGISTER_PDF:
            try:
                sql_location = SQLLocation.objects.get(location_id=location, domain=self.kwargs['domain'])
                locations = sql_location.get_ancestors(include_self=True)
                for loc in locations:
                    location_key = '%s_id' % loc.location_type.code
                    config.update({
                        location_key: loc.location_id,
                    })
                    beneficiary_config.update({
                        location_key: loc.location_id
                    })
            except SQLLocation.DoesNotExist:
                pass

        if indicator == ISSNIP_MONTHLY_REGISTER_PDF:
            awcs = request.POST.get('selected_awcs').split(',')
            location = request.POST.get('location', '')
            if 'all' in awcs and location:
                awcs = list(SQLLocation.objects.get(
                    location_id=location
                ).get_descendants().filter(
                    location_type__code=AWC_LOCATION_TYPE_CODE
                ).location_ids())
            pdf_format = request.POST.get('pdfformat')
            task = prepare_issnip_monthly_register_reports.delay(
                self.kwargs['domain'],
                awcs,
                pdf_format,
                month,
                year,
                request.couch_user,
            )
            task_id = task.task_id
            return JsonResponse(data={'task_id': task_id})
        if indicator == GROWTH_MONITORING_LIST_EXPORT:
            if not sql_location or sql_location.location_type_name in [LocationTypes.STATE]:
                return HttpResponseBadRequest()
            config = beneficiary_config
        if indicator == AWW_INCENTIVE_REPORT:
            if not sql_location or sql_location.location_type_name not in [
                LocationTypes.STATE, LocationTypes.DISTRICT, LocationTypes.BLOCK
            ]:
                return HttpResponseBadRequest()
            today = datetime.now(INDIA_TIMEZONE)
            month_offset = 2 if today.day < 15 else 1
            latest_year, latest_month = add_months(today.year, today.month, -month_offset)
            if year > latest_year or month > latest_month and year == latest_year:
                return HttpResponseBadRequest()
        if indicator == DASHBOARD_USAGE_EXPORT:
            config['couch_user'] = self.request.couch_user

        if indicator == SERVICE_DELIVERY_REPORT:
            config['beneficiary_category'] = request.POST.get('beneficiary_category')
        if indicator == THR_REPORT_EXPORT:
            config['thr_report_type'] = request.POST.get('thr_report_type')

        if indicator == CHILD_GROWTH_TRACKER_REPORT:
            if not sql_location or sql_location.location_type_name in [LocationTypes.STATE]:
                return HttpResponseBadRequest()
            config = beneficiary_config

        if indicator == POSHAN_PROGRESS_REPORT:
            config['report_layout'] = request.POST.get('report_layout')
            config['data_period'] = request.POST.get('data_period')
            config['quarter'] = int(request.POST.get('quarter'))
            config['year'] = year

        if indicator == AWW_ACTIVITY_REPORT:
            if not sql_location or sql_location.location_type_name not in [
                LocationTypes.STATE, LocationTypes.DISTRICT, LocationTypes.BLOCK, LocationTypes.SUPERVISOR
            ]:
                return HttpResponseBadRequest()
            config = beneficiary_config

        if indicator in (CHILDREN_EXPORT, PREGNANT_WOMEN_EXPORT, DEMOGRAPHICS_EXPORT, SYSTEM_USAGE_EXPORT,
                         AWC_INFRASTRUCTURE_EXPORT, GROWTH_MONITORING_LIST_EXPORT, AWW_INCENTIVE_REPORT,
                         LS_REPORT_EXPORT, THR_REPORT_EXPORT, DASHBOARD_USAGE_EXPORT,
                         SERVICE_DELIVERY_REPORT, CHILD_GROWTH_TRACKER_REPORT, AWW_ACTIVITY_REPORT,
                         POSHAN_PROGRESS_REPORT):
            task = prepare_excel_reports.delay(
                config,
                aggregation_level,
                include_test,
                icds_pre_release_features(self.request.couch_user),
                location,
                self.kwargs['domain'],
                export_format,
                indicator,
            )
            task_id = task.task_id
            return JsonResponse(data={'task_id': task_id})


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class FactSheetsView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location_id, selected_month = \
            self.get_settings(request, *args, **kwargs)

        aggregation_level = 1

        this_month = datetime(year, month, 1).date()
        two_before = this_month - relativedelta(months=2)

        config = {
            'aggregation_level': aggregation_level,
            'month': this_month,
            'previous_month': date.today().replace(day=1) - relativedelta(months=1),
            'two_before': two_before,
            'category': request.GET.get('category'),
            'domain': domain
        }

        config.update(get_location_filter(location_id, domain, include_object=True))

        # query database at same level for which it is requested
        if config.get('aggregation_level') > 1:
            config['aggregation_level'] -= 1

        loc_level = get_location_level(config.get('aggregation_level'))

        beta = icds_pre_release_features(request.user)
        data = FactSheetsReport(
            config=config, loc_level=loc_level, show_test=include_test, beta=beta
        ).get_data()
        return JsonResponse(data=data)


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class PrevalenceOfSevereView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = {}
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_severe_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_prevalence_of_severe_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_prevalence_of_severe_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_prevalence_of_severe_data_chart(domain, config, loc_level, include_test, icds_features_flag)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class PrevalenceOfStuntingView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = {}

        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_stunting_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_prevalence_of_stunting_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_prevalence_of_stunting_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_prevalence_of_stunting_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class NewbornsWithLowBirthWeightView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_newborn_with_low_birth_weight_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_newborn_with_low_birth_weight_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_newborn_with_low_birth_weight_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_newborn_with_low_birth_weight_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class EarlyInitiationBreastfeeding(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_early_initiation_breastfeeding_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_early_initiation_breastfeeding_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_early_initiation_breastfeeding_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_early_initiation_breastfeeding_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class ExclusiveBreastfeedingView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        config.update(get_location_filter(location, self.kwargs['domain']))

        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_exclusive_breastfeeding_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_exclusive_breastfeeding_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_exclusive_breastfeeding_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_exclusive_breastfeeding_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class ChildrenInitiatedView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_children_initiated_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_children_initiated_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_children_initiated_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_children_initiated_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class InstitutionalDeliveriesView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_institutional_deliveries_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_institutional_deliveries_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_institutional_deliveries_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_institutional_deliveries_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class ImmunizationCoverageView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_immunization_coverage_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_immunization_coverage_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_immunization_coverage_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_immunization_coverage_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@location_safe
@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class AWCDailyStatusView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow() - relativedelta(days=1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(now.timetuple())[:3],
            'aggregation_level': 1
        }
        location = request.GET.get('location_id', '')
        if location == 'null' or location == 'undefined':
            location = None
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_awc_daily_status_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_awc_daily_status_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_awc_daily_status_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_awc_daily_status_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class AWCsCoveredView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = get_awc_covered_data_with_retrying(step, domain, config, loc_level, location, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class RegisteredHouseholdView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_registered_household_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_registered_household_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_registered_household_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_registered_household_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class EnrolledChildrenView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_enrolled_children_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_enrolled_children_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_enrolled_children_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            if 'age' in config:
                del config['age']
            data = get_enrolled_children_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class EnrolledWomenView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_enrolled_women_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_enrolled_women_data_map(
                    domain, config.copy(), loc_level, include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_enrolled_women_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_enrolled_women_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class LactatingEnrolledWomenView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,

        }

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_lactating_enrolled_women_sector_data(
                    domain, config, loc_level, location, include_test, icds_features_flag
                )
            else:
                data = get_lactating_enrolled_women_data_map(
                    domain, config.copy(), loc_level,  include_test, icds_features_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_lactating_enrolled_women_sector_data(
                        domain, config, loc_level, location, include_test, icds_features_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_lactating_enrolled_data_chart(
                domain, config, loc_level, include_test, icds_features_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class AdolescentGirlsView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        pre_release_features = icds_pre_release_features(self.request.couch_user)
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adolescent_girls_sector_data(domain, config, loc_level, location, include_test,
                                                        pre_release_features)
            else:
                data = get_adolescent_girls_data_map(domain, config.copy(), loc_level, include_test,
                                                     pre_release_features)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_adolescent_girls_sector_data(
                        domain, config, loc_level, location, include_test, pre_release_features
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_adolescent_girls_data_chart(domain, config, loc_level, include_test, pre_release_features)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class AdhaarBeneficiariesView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        beta = icds_pre_release_features(request.couch_user)
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adhaar_sector_data(domain, config, loc_level, location, include_test, beta=beta)
            else:
                data = get_adhaar_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_adhaar_sector_data(domain, config, loc_level, location, include_test, beta=beta)
                    data.update(sector)
        elif step == "chart":
            data = get_adhaar_data_chart(domain, config, loc_level, include_test, beta=beta)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class CleanWaterView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_clean_water_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_clean_water_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_clean_water_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_clean_water_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class FunctionalToiletView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_functional_toilet_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_functional_toilet_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_functional_toilet_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_functional_toilet_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class MedicineKitView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_medicine_kit_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_medicine_kit_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_medicine_kit_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_medicine_kit_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class InfantometerView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_infantometer_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_infantometer_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_infantometer_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_infantometer_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })

@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class StadiometerView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_stadiometer_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_stadiometer_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_stadiometer_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_stadiometer_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })

@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class InfantsWeightScaleView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_infants_weight_scale_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_infants_weight_scale_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_infants_weight_scale_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_infants_weight_scale_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class AdultWeightScaleView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))
        beta = icds_pre_release_features(request.couch_user)

        if icds_pre_release_features(self.request.couch_user):
            config['num_launched_awcs__gte'] = 1
        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adult_weight_scale_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_adult_weight_scale_data_map(domain, config.copy(), loc_level, include_test, beta=beta)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_adult_weight_scale_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_adult_weight_scale_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })



@method_decorator([login_and_domain_required], name='dispatch')
class AggregationScriptPage(BaseDomainView):
    page_title = 'Aggregation Script'
    urlname = 'aggregation_script_page'
    template_name = 'icds_reports/aggregation_script.html'

    @use_daterangepicker
    def dispatch(self, *args, **kwargs):
        if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
            return HttpResponse("This page is only available for QA and not available for production instances.")

        couch_user = self.request.couch_user
        domain = self.domain
        domain_membership = couch_user.get_domain_membership(domain)
        bhd_role = UserRole.by_domain_and_name(
            domain, BHD_ROLE
        )
        if couch_user.is_domain_admin(domain) or (bhd_role or bhd_role[0].get_id == domain_membership.role_id):
            return super(AggregationScriptPage, self).dispatch(*args, **kwargs)
        else:
            raise PermissionDenied()

    def section_url(self):
        return

    def post(self, request, *args, **kwargs):
        date_param = self.request.POST.get('date')
        if not date_param:
            messages.error(request, 'Date is required')
            return redirect(self.urlname, domain=self.domain)
        date = force_to_date(date_param)
        move_ucr_data_into_aggregation_tables.delay(date)
        messages.success(request, 'Aggregation task is running. Data should appear soon.')
        return redirect(self.urlname, domain=self.domain)


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class DownloadExportReport(View):
    def get(self, request, *args, **kwargs):
        uuid = self.request.GET.get('uuid', None)
        file_format = self.request.GET.get('file_format', 'xlsx')
        content_type = Format.from_format(file_format)
        data_type = self.request.GET.get('data_type')
        icds_file = get_object_or_404(IcdsFile, blob_id=uuid)
        response = HttpResponse(
            icds_file.get_file_from_blobdb().read(),
            content_type=content_type.mimetype
        )
        response['Content-Disposition'] = safe_filename_header(data_type, content_type.extension)
        return response


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class DownloadPDFReport(View):
    def get(self, request, *args, **kwargs):
        uuid = self.request.GET.get('uuid', None)
        format = self.request.GET.get('format', None)
        icds_file = get_object_or_404(IcdsFile, blob_id=uuid, data_type='issnip_monthly')
        if format == 'one':
            response = HttpResponse(icds_file.get_file_from_blobdb().read(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="ICDS_CAS_monthly_register_cumulative.pdf"'
            return response
        else:
            response = HttpResponse(icds_file.get_file_from_blobdb().read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="ICDS_CAS_monthly_register.zip"'
            return response


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class CheckExportReportStatus(View):
    def get(self, request, *args, **kwargs):
        task_id = self.request.GET.get('task_id', None)
        res = AsyncResult(task_id) if task_id else None
        status = res and res.ready()

        if status:
            return JsonResponse(
                {
                    'task_ready': status,
                    'task_successful': res.successful(),
                    'task_result': res.result if res.successful() else None
                }
            )
        return JsonResponse({'task_ready': status})


@location_safe
class ICDSImagesAccessorAPI(View):
    @method_decorator(api_auth)
    @method_decorator(require_permission(
        Permissions.view_report, 'custom.icds_reports.reports.reports.DashboardReport'))
    def get(self, request, domain, form_id=None, attachment_id=None):
        if not form_id or not attachment_id:
            raise Http404
        try:
            content = FormAccessors(domain).get_attachment_content(form_id, attachment_id)
        except AttachmentNotFound:
            raise Http404
        if 'image' not in content.content_type:
            raise Http404
        return StreamingHttpResponse(
            streaming_content=FileWrapper(content.content_stream),
            content_type=content.content_type
        )


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class InactiveAWW(View):
    def get(self, request, *args, **kwargs):
        sync_date = request.GET.get('date', None)
        if sync_date:
            sync = IcdsFile.objects.filter(file_added=sync_date).first()
        else:
            sync = IcdsFile.objects.filter(data_type='inactive_awws').order_by('-file_added').first()
        zip_name = 'inactive_awws_%s' % sync.file_added.strftime('%Y-%m-%d')
        try:
            return export_response(sync.get_file_from_blobdb(), 'csv', zip_name)
        except NotFound:
            raise Http404


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class InactiveDashboardUsers(View):
    def get(self, request, *args, **kwargs):
        sync_date = request.GET.get('date', None)
        if sync_date:
            sync = IcdsFile.objects.filter(file_added=sync_date).first()
        else:
            sync = IcdsFile.objects.filter(data_type='inactive_dashboard_users').order_by('-file_added').first()
        zip_name = 'inactive_dashboard_users_%s' % sync.file_added.strftime('%Y-%m-%d')
        try:
            return export_response(sync.get_file_from_blobdb(), 'zip', zip_name)
        except NotFound:
            raise Http404


@location_safe
class DishaAPIView(BaseCasAPIView):

    def message(self, message_name):
        state_names = ", ".join(self.valid_state_names)
        error_messages = {
            "missing_date": "Please specify valid month and year",
            "invalid_month": "Please specify a month that's older than a month and 5 days",
            "invalid_state": "Please specify one of {} as state_name".format(state_names),
        }
        return {"message": error_messages[message_name]}

    @method_decorator([api_auth, toggles.ICDS_DISHA_API.required_decorator()])
    def get(self, request, *args, **kwargs):

        valid_query_month, error_message = self.get_valid_query_month(request.GET.get('month'),
                                                                      request.GET.get('year'))

        if error_message:
            return JsonResponse(self.message('missing_date'), status=400)

        # Can return only one month old data if today is after 5th, otherwise
        #   can return two month's old data
        today = date.today()
        current_month = today - relativedelta(months=1) if today.day <= 5 else today
        if valid_query_month > current_month or valid_query_month < date(2017, 1, 1):
            return JsonResponse(self.message('invalid_month'), status=400)

        state_name = self.request.GET.get('state_name')
        if state_name not in self.valid_state_names:
            return JsonResponse(self.message('invalid_state'), status=400)

        dump = DishaDump(state_name, valid_query_month)
        return dump.get_export_as_http_response(request)

    @property
    @icds_quickcache([])
    def valid_state_names(self):
        return list(AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE, state_is_test=0).values_list('state_name', flat=True))


@location_safe
@method_decorator([api_auth, toggles.ICDS_NIC_INDICATOR_API.required_decorator()], name='dispatch')
class NICIndicatorAPIView(View):

    def message(self, message_name):
        error_messages = {
            "unknown_error": "Unknown Error occured",
            "no_data": "Data does not exists"
        }

        return error_messages[message_name]

    def get(self, request, *args, **kwargs):

        try:
            data = get_inc_indicator_api_data()
            response = {'isSuccess': True,
                        'message': 'Data Sent Successfully',
                        'Result': {
                            'response': data
                        }}
            return JsonResponse(response)
        except NICIndicatorsView.DoesNotExist:
            response = dict(isSuccess=False, message=self.message('no_data'))
            return JsonResponse(response, status=500)
        except AttributeError:
            response = dict(isSuccess=False, message=self.message('unknown_error'))
            return JsonResponse(response, status=500)

    @property
    @icds_quickcache([])
    def valid_states(self):
        states = AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE,
                                            state_is_test=0).values_list('state_name', 'state_id')
        return {state[0]: state[1] for state in states}


@location_safe
@method_decorator([api_auth, toggles.AP_WEBSERVICE.required_decorator()], name='dispatch')
class APWebservice(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'message': 'Connection Successful'})


@method_decorator([login_and_domain_required, toggles.DAILY_INDICATORS.required_decorator()], name='dispatch')
class DailyIndicators(View):
    def get(self, request, *args, **kwargs):

        try:
            filename, export_file = get_daily_indicators()
        except AggAwcDailyView.DoesNotExist:
            return JsonResponse({'message': 'No data for Yesterday'}, status=500)
        response = HttpResponse(export_file.read(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        return response


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class CasDataExport(View):
    def post(self, request, *args, **kwargs):
        data_type = request.POST.get('indicator', None)
        location_id = request.POST.get('location', None)
        month = int(request.POST.get('month', None))
        year = int(request.POST.get('year', None))
        selected_date = date(year, month, 1).strftime('%Y-%m-%d')

        if location_id and not user_can_access_location_id(
                self.kwargs['domain'], request.couch_user, location_id
        ):
            return JsonResponse({"message": "Sorry, you do not have access to that location."})

        location = SQLLocation.objects.select_related('location_type').get(location_id=location_id)
        state = location
        while not state.location_type.name == 'state':
            state = state.parent
        sync, blob_id = get_cas_data_blob_file(data_type, state.location_id, selected_date)
        if not sync:
            return JsonResponse({"message": "Sorry, the export you requested does not exist."})
        else:
            if state != location:
                # check for cached version
                cached_sync, blob_id = get_cas_data_blob_file(data_type, location_id, selected_date)
                if not cached_sync:
                    try:
                        export_file = filter_cas_data_export(sync, location)
                    except InvalidLocationTypeException as e:
                        return JsonResponse({"message": e})
                    with open(export_file, 'rb') as csv_file:
                        blob_id = f'{data_type}-{location_id}-{selected_date}'
                        THREE_DAYS = 60 * 60 * 24 * 3
                        icds_file, new = IcdsFile.objects.get_or_create(blob_id=blob_id, data_type=f'mbt_{data_type}')
                        icds_file.store_file_in_blobdb(csv_file, expired=THREE_DAYS)
            params = dict(
                indicator=data_type,
                location=location_id,
                month=month,
                year=year
            )
            return JsonResponse(
                {
                    "report_link": reverse(
                        'cas_export',
                        params=params,
                        absolute=True,
                        kwargs={'domain': self.kwargs['domain']}
                    )
                }
            )

    def get(self, request, *args, **kwargs):
        data_type = request.GET.get('indicator', None)
        location_id = request.GET.get('location', None)
        month = int(request.GET.get('month', None))
        year = int(request.GET.get('year', None))
        selected_date = date(year, month, 1).strftime('%Y-%m-%d')

        if location_id and not user_can_access_location_id(
                self.kwargs['domain'], request.couch_user, location_id
        ):
            return HttpResponse(status_code=403)
        sync, csv_name = get_cas_data_blob_file(data_type, location_id, selected_date)
        data = sync.get_file_from_blobdb()
        try:
            return export_response(data, 'unzipped-csv', csv_name)
        except NotFound:
            raise Http404


@location_safe
class CasDataExportAPIView(View):

    def message(self, message_name):
        state_names = ", ".join(self.valid_state_names)
        types = ", ".join(self.valid_types)
        error_messages = {
            "missing_date": "Please specify valid month and year",
            "invalid_month": "Please specify a month that's older than a month and 5 days",
            "invalid_state": "Please specify one of {} as state_name".format(state_names),
            "invalid_type": "Please specify one of {} as data_type".format(types),
            "not_available": "The file you have requested is no longer available",
            "no_access": "You do not have access to this state"
        }
        return {"message": error_messages[message_name]}

    @method_decorator([api_auth])
    def get(self, request, *args, **kwargs):
        try:
            month = int(request.GET.get('month'))
            year = int(request.GET.get('year'))
        except (ValueError, TypeError):
            return JsonResponse(self.message('missing_date'), status=400)

        query_month = date(year, month, 1)
        today = date.today()
        available_month = today - relativedelta(months=2) if today.day <= 15 else today - relativedelta(months=1)
        if query_month > available_month:
            return JsonResponse(self.message('invalid_month'), status=400)

        selected_date = date(year, month, 1).strftime('%Y-%m-%d')

        state_name = self.request.GET.get('state_name')
        if state_name not in self.valid_state_names:
            return JsonResponse(self.message('invalid_state'), status=400)

        user_states = [loc.name
                       for loc in self.request.couch_user.get_sql_locations(self.request.domain)
                       if loc.location_type.name == 'state']
        if state_name not in user_states and not self.request.couch_user.has_permission(self.request.domain, 'access_all_locations'):
            return JsonResponse(self.message('no_access'), status=403)

        state_id = SQLLocation.objects.get(location_type__name='state', name=state_name, domain=self.request.domain).location_id

        data_type = request.GET.get('type')
        if data_type not in self.valid_types:
            return JsonResponse(self.message('invalid_type'), status=400)
        type_code = CasDataExportAPIView.get_type_code(data_type)

        sync, blob_id = get_cas_data_blob_file(type_code, state_id, selected_date)

        try:
            return export_response(sync.get_file_from_blobdb(), 'unzipped-csv', blob_id)
        except NotFound:
            return JsonResponse(self.message('not_available'), status=400)

    @property
    @icds_quickcache([])
    def valid_state_names(self):
        return list(AwcLocation.objects.filter(
            aggregation_level=AggregationLevels.STATE, state_is_test=0
        ).values_list('state_name', flat=True))

    @property
    def valid_types(self):
        return ('woman', 'child', 'awc')

    @staticmethod
    def get_type_code(data_type):
        type_map = {
            "child": 'child_health_monthly',
            "woman": 'ccs_record_monthly',
            "awc": 'agg_awc',
        }
        return type_map[data_type]


@location_safe
@method_decorator([api_auth, toggles.mwcd_indicators.required_decorator()], name='dispatch')
class MWCDDataView(View):

    def get(self, request, *args, **kwargs):
        try:
            data = get_mwcd_indicator_api_data()
            response = {'isSuccess': True,
                        'message': 'Data Sent Successfully',
                        'Result': {
                            'response': data
                        }}
            return JsonResponse(response)
        except Exception:
            response = dict(isSuccess=False, message='Unknown Error occured')
            return JsonResponse(response, status=500)


@location_safe
@method_decorator([api_auth, toggles.ICDS_GOVERNANCE_DASHABOARD_API.required_decorator()], name='dispatch')
class GovernanceAPIBaseView(View):

    @staticmethod
    def get_state_id_from_state_site_code(state_code):
        awc_location = AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE,
                                                  state_site_code=state_code, state_is_test=0)\
            .values_list('state_id', flat=True)
        return awc_location[0] if len(awc_location) > 0 else None

    def get_gov_api_params(self, request):
        month = int(request.GET.get('month'))
        year = int(request.GET.get('year'))
        state_site_code = request.GET.get('state_site_code')
        state_id = None
        if state_site_code is not None:
            state_id = GovernanceAPIBaseView.get_state_id_from_state_site_code(state_site_code)

        last_awc_id = request.GET.get('last_awc_id', '')
        return last_awc_id, month, year, state_id

    def validate_param(self, state_id, month, year):
        selected_month = date(year, month, 1)
        current_month = date.today().replace(day=1)

        is_valid = True
        error_message = ''
        if not (date(2019, 4, 1) <= selected_month <= current_month):
            is_valid = False
            error_message = "Month should not be in future and can only be from April 2019"
        if state_id is None:
            is_valid = False
            error_message = "Invalid State code"

        return is_valid, error_message


class GovernanceHomeVisitAPI(GovernanceAPIBaseView):

    def get(self, request, *args, **kwargs):
        last_awc_id, month, year, state_id = self.get_gov_api_params(request)
        is_valid, error_message = self.validate_param(state_id, month, year)

        if not is_valid:
            return HttpResponse(error_message, status=400)

        query_filters = {'aggregation_level': AggregationLevels.AWC,
                         'num_launched_awcs': 1,
                         'awc_id__gt': last_awc_id,
                         'state_id': state_id
                         }
        order = ['awc_id']

        data, count = get_home_visit_data(
            CAS_API_PAGE_SIZE,
            year,
            month,
            order,
            query_filters
        )
        response_json = {
            'data': data,
            'metadata': {
                'month': month,
                'year': year,
                'count': count,
                'timestamp': india_now()
            }
        }
        return JsonResponse(data=response_json)


class GovernanceBeneficiaryAPI(GovernanceAPIBaseView):

    def get(self, request, *args, **kwargs):
        last_awc_id, month, year, state_id = self.get_gov_api_params(request)
        is_valid, error_message = self.validate_param(state_id, month, year)

        if not is_valid:
            return HttpResponse(error_message, status=400)

        query_filters = {
            'state_id': state_id,
            'awc_launched': 1,
            'awc_id__gt': last_awc_id}
        order = ['awc_id']

        data, count = get_beneficiary_data(
            CAS_API_PAGE_SIZE,
            year,
            month,
            order,
            query_filters
        )

        response_json = {
            'data': data,
            'metadata': {
                'month': month,
                'year': year,
                'count': count,
                'timestamp': india_now()
            }
        }
        return JsonResponse(data=response_json)


class GovernanceStateListAPI(GovernanceAPIBaseView):

    def get(self, request, *args, **kwargs):
        return JsonResponse(data={'data': get_state_names()})


class GovernanceVHNDSAPI(GovernanceAPIBaseView):

    def get(self, request, *args, **kwargs):
        last_awc_id, month, year, state_id = self.get_gov_api_params(request)
        is_valid, error_message = self.validate_param(state_id, month, year)

        if not is_valid:
            return HttpResponse(error_message, status=400)

        query_filters = {'awc_id__gt': last_awc_id, 'awc_launched': True}
        order = ['awc_id']
        if state_id is not None:
            query_filters['state_id'] = state_id
        data, count = get_vhnd_data(CAS_API_PAGE_SIZE, year,
                                    month, order, query_filters)
        response_json = {
            'data': data,
            'metadata': {
                'month': month,
                'year': year,
                'count': count,
                'timestamp': india_now()
            }
        }
        return JsonResponse(data=response_json)


class GovernanceCBEAPI(GovernanceAPIBaseView):

    def get(self, request, *args, **kwargs):
        last_awc_id, month, year, state_id = self.get_gov_api_params(request)
        is_valid, error_message = self.validate_param(state_id, month, year)

        if not is_valid:
            return HttpResponse(error_message, status=400)

        query_filters = {
            'state_id': state_id,
            'awc_launched': True,
            'awc_id__gt': last_awc_id}
        order = ['awc_id']

        data, count = get_cbe_data(
            CAS_API_PAGE_SIZE,
            year,
            month,
            order,
            query_filters
        )

        response_json = {
            'data': data,
            'metadata': {
                'month': month,
                'year': year,
                'count': count,
                'timestamp': india_now()
            }
        }
        return JsonResponse(data=response_json)


@location_safe
@method_decorator([api_auth, toggles.ICDS_BIHAR_DEMOGRAPHICS_API.required_decorator()], name='dispatch')
class BiharDemographicsAPI(BaseCasAPIView):
    def message(self, message_name):
        error_messages = {
            "invalid_month": "Please specify a valid month. Month can't be in future and before Jan 2020",
            "access_denied": "You are not authorised to access this location"
        }
        return {"message": error_messages[message_name]}

    def get(self, request, *args, **kwargs):

        last_person_case_id = request.GET.get('last_person_case_id', '')

        valid_query_month, error_message = self.get_valid_query_month(request.GET.get('month'),
                                                                      request.GET.get('year'))
        bihar_state_id = self.get_state_id_from_state_name('Bihar')
        if error_message:
            return JsonResponse({"message": error_message}, status=400)

        if not self.query_month_in_range(valid_query_month, start_month=date(2020, 1, 1)):
            return JsonResponse(self.message('invalid_month'), status=400)

        if not self.has_access(bihar_state_id, request.couch_user):
            return JsonResponse(self.message('access_denied'), status=403)

        demographics_data, total_count = get_api_demographics_data(valid_query_month.strftime("%Y-%m-%d"),
                                                                   bihar_state_id,
                                                                   last_person_case_id)
        response_json = {
            'data': demographics_data,
            'metadata': {
                'month': valid_query_month.month,
                'year': valid_query_month.year,
                'total_count': total_count,
                'timestamp': india_now()
            }
        }

        return JsonResponse(data=response_json)


@location_safe
@method_decorator([api_auth, toggles.ICDS_BIHAR_DEMOGRAPHICS_API.required_decorator()], name='dispatch')
class BiharVaccinesAPI(BaseCasAPIView):
    def message(self, message_name):
        error_messages = {
            "invalid_month": "Please specify a valid month. Month can't be in future and before Jan 2020",
            "access_denied": "You are not authorised to access this location"
        }
        return {"message": error_messages[message_name]}

    def get(self, request, *args, **kwargs):

        last_person_case_id = request.GET.get('last_person_case_id', '')

        valid_query_month, error_message = self.get_valid_query_month(request.GET.get('month'),
                                                                      request.GET.get('year'))
        bihar_state_id = self.get_state_id_from_state_name('Bihar')
        if error_message:
            return JsonResponse({"message": error_message}, status=400)

        if not self.query_month_in_range(valid_query_month, start_month=date(2020, 1, 1)):
            return JsonResponse(self.message('invalid_month'), status=400)

        if not self.has_access(bihar_state_id, request.couch_user):
            return JsonResponse(self.message('access_denied'), status=403)

        vaccines_data, total_count = get_api_vaccine_data(valid_query_month.strftime("%Y-%m-%d"),
                                                          bihar_state_id,
                                                          last_person_case_id)
        response_json = {
            'data': vaccines_data,
            'metadata': {
                'month': valid_query_month.month,
                'year': valid_query_month.year,
                'total_count': total_count,
                'timestamp': india_now()
            }
        }

        return JsonResponse(data=response_json)

@location_safe
@method_decorator([api_auth, toggles.ICDS_BIHAR_DEMOGRAPHICS_API.required_decorator()], name='dispatch')
class BiharSchoolAPI(BaseCasAPIView):
    def message(self, message_name):
        error_messages = {
            "invalid_month": "Please specify a valid month. Month can't be in future and before Jan 2020",
            "access_denied": "You are not authorised to access this location"
        }
        return {"message": error_messages[message_name]}

    def get(self, request, *args, **kwargs):

        last_person_case_id = request.GET.get('last_person_case_id', '')

        valid_query_month, error_message = self.get_valid_query_month(request.GET.get('month'),
                                                                      request.GET.get('year'))
        bihar_state_id = self.get_state_id_from_state_name('Bihar')

        if error_message:
            return JsonResponse({"message": error_message}, status=400)

        if not self.query_month_in_range(valid_query_month, start_month=date(2020, 1, 1)):
            return JsonResponse(self.message('invalid_month'), status=400)

        if not self.has_access(bihar_state_id, request.couch_user):
            return JsonResponse(self.message('access_denied'), status=403)

        school_data, total_count = get_api_ag_school_data(valid_query_month.strftime("%Y-%m-%d"),
                                                          bihar_state_id,
                                                          last_person_case_id)
        response_json = {
            'data': school_data,
            'metadata': {
                'month': valid_query_month.month,
                'year': valid_query_month.year,
                'total_count': total_count,
                'timestamp': india_now()
            }
        }

        return JsonResponse(data=response_json)


@location_safe
@method_decorator([api_auth, toggles.ICDS_BIHAR_DEMOGRAPHICS_API.required_decorator()], name='dispatch')
class BiharMotherDetailsAPI(BaseCasAPIView):
    def message(self, message_name):
        error_messages = {
            "invalid_month": "Please specify a valid month. Month can't be in future and before Jan 2020",
            "access_denied": "You are not authorised to access this location"
        }
        return {"message": error_messages[message_name]}

    def get(self, request, *args, **kwargs):

        last_ccs_case_id = request.GET.get('last_ccs_case_id', '')

        valid_query_month, error_message = self.get_valid_query_month(request.GET.get('month'),
                                                                      request.GET.get('year'))
        bihar_state_id = self.get_state_id_from_state_name('Bihar')

        if error_message:
            return JsonResponse({"message": error_message}, status=400)

        if not self.query_month_in_range(valid_query_month, start_month=date(2020, 1, 1)):
            return JsonResponse(self.message('invalid_month'), status=400)

        if not self.has_access(bihar_state_id, request.couch_user):
            return JsonResponse(self.message('access_denied'), status=403)

        demographics_data, total_count = get_mother_details(valid_query_month.strftime("%Y-%m-%d"),
                                                            bihar_state_id,
                                                            last_ccs_case_id)
        response_json = {
            'data': demographics_data,
            'metadata': {
                'month': valid_query_month.month,
                'year': valid_query_month.year,
                'total_count': total_count,
                'timestamp': india_now()
            }
        }

        return JsonResponse(data=response_json)


@method_decorator(DASHBOARD_CHECKS, name='dispatch')
class PoshanProgressDashboardView(BaseReportView):
    def get_settings(self, request, *args, **kwargs):
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))

        include_test = request.GET.get('include_test', False)
        domain = self.kwargs['domain']
        location = request.GET.get('location_id')
        if location == 'null' or location == 'undefined':
            location = None
        data_format = request.GET.get('data_format', 'month')
        quarter = int(request.GET.get('quarter', 1))

        return step, month, year, include_test, domain, data_format, quarter, location

    def get(self, request, *args, **kwargs):
        step, month, year, include_test, domain, data_format, quarter, location = \
            self.get_settings(request, *args, **kwargs)

        location_filters = get_location_filter(location, domain)
        location_filters['aggregation_level'] = location_filters.get('aggregation_level', 1)

        icds_features_flag = icds_pre_release_features(self.request.couch_user)
        data = {}
        if icds_features_flag:
            data = get_poshan_progress_dashboard_data(
                domain,
                year,
                month,
                quarter,
                data_format,
                step,
                location_filters,
                include_test
            )
        return JsonResponse(data=data)
