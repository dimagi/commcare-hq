from __future__ import absolute_import

from __future__ import unicode_literals

from collections import OrderedDict
from wsgiref.util import FileWrapper

import requests
from lxml import etree


from datetime import datetime, date
from celery.result import AsyncResult
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models.query_utils import Q
from django.http.response import JsonResponse, HttpResponseBadRequest, HttpResponse, StreamingHttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from corehq.util.view_utils import reverse
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView, RedirectView

from corehq import toggles
from corehq.apps.cloudcare.utils import webapps_module
from corehq.apps.domain.decorators import login_and_domain_required, api_auth
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.views import BugReportView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, user_can_access_location_id
from corehq.apps.locations.util import location_hierarchy_config
from corehq.apps.hqwebapp.decorators import (
    use_daterangepicker,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import UserRole, Permissions
from corehq.blobs.exceptions import NotFound
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.util.files import safe_filename_header
from custom.icds.const import AWC_LOCATION_TYPE_CODE
from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, BHD_ROLE, ICDS_SUPPORT_EMAIL, CHILDREN_EXPORT, \
    PREGNANT_WOMEN_EXPORT, DEMOGRAPHICS_EXPORT, SYSTEM_USAGE_EXPORT, AWC_INFRASTRUCTURE_EXPORT, \
    BENEFICIARY_LIST_EXPORT, ISSNIP_MONTHLY_REGISTER_PDF, AWW_INCENTIVE_REPORT, INDIA_TIMEZONE, LS_REPORT_EXPORT, \
    THR_REPORT_EXPORT
from custom.icds_reports.const import AggregationLevels
from custom.icds_reports.models.aggregate import AwcLocation
from custom.icds_reports.models.helper import IcdsFile
from custom.icds_reports.queries import get_cas_data_blob_file
from custom.icds_reports.reports.adhaar import get_adhaar_data_chart, get_adhaar_data_map, get_adhaar_sector_data
from custom.icds_reports.reports.adolescent_girls import get_adolescent_girls_data_map, \
    get_adolescent_girls_sector_data, get_adolescent_girls_data_chart
from custom.icds_reports.reports.adult_weight_scale import get_adult_weight_scale_data_chart, \
    get_adult_weight_scale_data_map, get_adult_weight_scale_sector_data
from custom.icds_reports.reports.awc_daily_status import get_awc_daily_status_data_chart,\
    get_awc_daily_status_data_map, get_awc_daily_status_sector_data
from custom.icds_reports.reports.awc_reports import get_awc_report_beneficiary, get_awc_report_demographics, \
    get_awc_reports_maternal_child, get_awc_reports_pse, get_awc_reports_system_usage, get_beneficiary_details, \
    get_awc_report_infrastructure, get_awc_report_pregnant, get_pregnant_details, get_awc_report_lactating
from custom.icds_reports.reports.awcs_covered import get_awcs_covered_data_map, get_awcs_covered_sector_data, \
    get_awcs_covered_data_chart
from custom.icds_reports.reports.children_initiated_data import get_children_initiated_data_chart, \
    get_children_initiated_data_map, get_children_initiated_sector_data
from custom.icds_reports.reports.clean_water import get_clean_water_data_map, get_clean_water_data_chart, \
    get_clean_water_sector_data
from custom.icds_reports.reports.disha import DishaDump
from custom.icds_reports.reports.early_initiation_breastfeeding import get_early_initiation_breastfeeding_chart,\
    get_early_initiation_breastfeeding_data, get_early_initiation_breastfeeding_map
from custom.icds_reports.reports.enrolled_children import get_enrolled_children_data_chart,\
    get_enrolled_children_data_map, get_enrolled_children_sector_data
from custom.icds_reports.reports.enrolled_women import get_enrolled_women_data_map, \
    get_enrolled_women_sector_data, get_enrolled_women_data_chart
from custom.icds_reports.reports.exclusive_breastfeeding import get_exclusive_breastfeeding_data_chart, \
    get_exclusive_breastfeeding_data_map, get_exclusive_breastfeeding_sector_data
from custom.icds_reports.reports.fact_sheets import FactSheetsReport
from custom.icds_reports.reports.functional_toilet import get_functional_toilet_data_chart,\
    get_functional_toilet_data_map, get_functional_toilet_sector_data
from custom.icds_reports.reports.immunization_coverage_data import get_immunization_coverage_data_chart, \
    get_immunization_coverage_data_map, get_immunization_coverage_sector_data
from custom.icds_reports.reports.infants_weight_scale import get_infants_weight_scale_data_chart, \
    get_infants_weight_scale_data_map, get_infants_weight_scale_sector_data
from custom.icds_reports.reports.institutional_deliveries_sector import get_institutional_deliveries_data_chart,\
    get_institutional_deliveries_data_map, get_institutional_deliveries_sector_data
from custom.icds_reports.reports.lactating_enrolled_women import get_lactating_enrolled_women_data_map, \
    get_lactating_enrolled_women_sector_data, get_lactating_enrolled_data_chart
from custom.icds_reports.reports.lady_supervisor import get_lady_supervisor_data
from custom.icds_reports.reports.medicine_kit import get_medicine_kit_data_chart, get_medicine_kit_data_map, \
    get_medicine_kit_sector_data
from custom.icds_reports.reports.new_born_with_low_weight import get_newborn_with_low_birth_weight_chart, \
    get_newborn_with_low_birth_weight_data, get_newborn_with_low_birth_weight_map
from custom.icds_reports.reports.prevalence_of_severe import get_prevalence_of_severe_data_chart,\
    get_prevalence_of_severe_data_map, get_prevalence_of_severe_sector_data
from custom.icds_reports.reports.prevalence_of_stunting import get_prevalence_of_stunting_data_chart, \
    get_prevalence_of_stunting_data_map, get_prevalence_of_stunting_sector_data
from custom.icds_reports.reports.prevalence_of_undernutrition import get_prevalence_of_undernutrition_data_chart,\
    get_prevalence_of_undernutrition_data_map, get_prevalence_of_undernutrition_sector_data
from custom.icds_reports.reports.registered_household import get_registered_household_data_map, \
    get_registered_household_sector_data, get_registered_household_data_chart
from custom.icds_reports.reports.service_delivery_dashboard import get_service_delivery_data
from custom.icds_reports.tasks import move_ucr_data_into_aggregation_tables, \
    prepare_issnip_monthly_register_reports, prepare_excel_reports
from custom.icds_reports.utils import get_age_filter, get_location_filter, \
    get_latest_issue_tracker_build_id, get_location_level, icds_pre_release_features, \
    current_month_stunting_column, current_month_wasting_column, get_age_filter_in_months, \
    get_datatables_ordering_info
from custom.icds_reports.utils.data_accessor import get_program_summary_data,\
    get_program_summary_data_with_retrying
from dimagi.utils.dates import force_to_date, add_months
from . import const
from .exceptions import TableauTokenException
from couchexport.shortcuts import export_response
from couchexport.export import Format
from custom.icds_reports.utils.data_accessor import get_inc_indicator_api_data
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.models.views import NICIndicatorsView
from django.views.decorators.csrf import csrf_exempt


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class TableauView(RedirectView):

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
@method_decorator([toggles.DASHBOARD_ICDS_REPORT.required_decorator(), login_and_domain_required], name='dispatch')
class DashboardView(TemplateView):
    template_name = 'icds_reports/dashboard.html'

    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def couch_user(self):
        return self.request.couch_user

    def _has_helpdesk_role(self):
        user_roles = UserRole.by_domain(self.domain)
        helpdesk_roles_id = [
            role.get_id
            for role in user_roles
            if role.name in const.HELPDESK_ROLES
        ]
        domain_membership = self.couch_user.get_domain_membership(self.domain)
        return domain_membership.role_id in helpdesk_roles_id

    def get_context_data(self, **kwargs):
        kwargs.update(self.kwargs)
        kwargs['location_hierarchy'] = location_hierarchy_config(self.domain)
        kwargs['user_location_id'] = self.couch_user.get_location_id(self.domain)
        kwargs['all_user_location_id'] = list(self.request.couch_user.get_sql_locations(
            self.kwargs['domain']
        ).location_ids())
        kwargs['state_level_access'] = 'state' in set(
            [loc.location_type.code for loc in self.request.couch_user.get_sql_locations(
                self.kwargs['domain']
            )]
        )
        kwargs['have_access_to_features'] = icds_pre_release_features(self.couch_user)
        kwargs['have_access_to_all_locations'] = self.couch_user.has_permission(
            self.domain, 'access_all_locations'
        )
        is_commcare_user = self.couch_user.is_commcare_user()

        if self.couch_user.is_web_user():
            kwargs['is_web_user'] = True
        elif is_commcare_user and self._has_helpdesk_role():
            build_id = get_latest_issue_tracker_build_id()
            kwargs['report_an_issue_url'] = webapps_module(
                domain=self.domain,
                app_id=build_id,
                module_id=0,
            )
        return super(DashboardView, self).get_context_data(**kwargs)


@location_safe
class IcdsDynamicTemplateView(TemplateView):

    def get_template_names(self):
        return ['icds_reports/icds_app/%s.html' % self.kwargs['template']]


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


@method_decorator([login_and_domain_required], name='dispatch')
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


@method_decorator([login_and_domain_required], name='dispatch')
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


@method_decorator([login_and_domain_required], name='dispatch')
class ServiceDeliveryDashboardView(BaseReportView):

    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        location_filters = get_location_filter(location, domain)
        location_filters['aggregation_level'] = location_filters.get('aggregation_level', 1)

        start, length, order_by_number_column, order_by_name_column, order_dir = \
            get_datatables_ordering_info(request)
        reversed_order = True if order_dir == 'desc' else False

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


@method_decorator([login_and_domain_required], name='dispatch')
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

        config.update(get_location_filter(location, domain))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_undernutrition_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_prevalence_of_undernutrition_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_prevalence_of_undernutrition_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_prevalence_of_undernutrition_data_chart(domain, config, loc_level, include_test)

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

            map_location_name = location.name
            if 'map_location_name' in location.metadata and location.metadata['map_location_name']:
                map_location_name = location.metadata['map_location_name']
            return JsonResponse({
                'name': location.name,
                'map_location_name': map_location_name,
                'location_type': location.location_type.code,
                'location_type_name': location.location_type_name,
                'user_have_access': user_can_access_location_id(
                    self.kwargs['domain'],
                    request.couch_user, location.location_id
                ),
                'user_have_access_to_parent': location.location_id in parent_ids
            })

        parent_id = request.GET.get('parent_id')
        name = request.GET.get('name')

        show_test = request.GET.get('include_test', False)

        locations = SQLLocation.objects.accessible_to_user(self.kwargs['domain'], self.request.couch_user)
        if not parent_id:
            locations = locations.filter(parent_id__isnull=True)
        else:
            locations = locations.filter(parent__location_id=parent_id)

        if locations.count() == 0:
            locations = user_locations_with_parents.filter(parent__location_id=parent_id)

        if name:
            locations = locations.filter(name__iexact=name)

        locations = locations.order_by('name')
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
                    'user_have_access_to_parent': loc.location_id in parent_ids
                }
                for loc in locations if show_test or loc.metadata.get('is_test_location', 'real') != 'test'
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
                    'user_have_access_to_parent': location.location_id in parent_locations_ids
                }
                for location in list(OrderedDict.fromkeys(list(locations) + list(parents)))
                if show_test or location.metadata.get('is_test_location', 'real') != 'test'
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
                'user_have_access_to_parent': selected_location.location_id in parent_locations_ids
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


@method_decorator([login_and_domain_required], name='dispatch')
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
            filters = {
                'awc_id': config['awc_id'],
            }
            age = self.request.GET.get('age', None)
            if age:
                filters.update(get_age_filter_in_months(age))
            if 'awc_id' in config:
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
                request.couch_user
            )
            task_id = task.task_id
            return JsonResponse(data={'task_id': task_id})
        if indicator == BENEFICIARY_LIST_EXPORT:
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
        if indicator in (CHILDREN_EXPORT, PREGNANT_WOMEN_EXPORT, DEMOGRAPHICS_EXPORT, SYSTEM_USAGE_EXPORT,
                         AWC_INFRASTRUCTURE_EXPORT, BENEFICIARY_LIST_EXPORT, AWW_INCENTIVE_REPORT,
                         LS_REPORT_EXPORT, THR_REPORT_EXPORT):
            task = prepare_excel_reports.delay(
                config,
                aggregation_level,
                include_test,
                icds_pre_release_features(self.request.couch_user),
                location,
                self.kwargs['domain'],
                export_format,
                indicator
            )
            task_id = task.task_id
            return JsonResponse(data={'task_id': task_id})


@method_decorator([login_and_domain_required], name='dispatch')
class FactSheetsView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
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

        config.update(get_location_filter(location, domain))
        loc_level = get_location_level(config.get('aggregation_level'))

        beta = icds_pre_release_features(request.user)
        data = FactSheetsReport(
            config=config, loc_level=loc_level, show_test=include_test, beta=beta
        ).get_data()
        return JsonResponse(data=data)


@method_decorator([login_and_domain_required], name='dispatch')
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
        icds_futures_flag = icds_pre_release_features(self.request.couch_user)
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_severe_sector_data(
                    domain, config, loc_level, location, include_test, icds_futures_flag
                )
            else:
                data = get_prevalence_of_severe_data_map(
                    domain, config.copy(), loc_level, include_test, icds_futures_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_prevalence_of_severe_sector_data(
                        domain, config, loc_level, location, include_test, icds_futures_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_prevalence_of_severe_data_chart(domain, config, loc_level, include_test, icds_futures_flag)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        icds_futures_flag = icds_pre_release_features(self.request.couch_user)
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_stunting_sector_data(
                    domain, config, loc_level, location, include_test, icds_futures_flag
                )
            else:
                data = get_prevalence_of_stunting_data_map(
                    domain, config.copy(), loc_level, include_test, icds_futures_flag
                )
                if loc_level == LocationTypes.BLOCK:
                    sector = get_prevalence_of_stunting_sector_data(
                        domain, config, loc_level, location, include_test, icds_futures_flag
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_prevalence_of_stunting_data_chart(
                domain, config, loc_level, include_test, icds_futures_flag
            )

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_newborn_with_low_birth_weight_data(domain, config, loc_level, location, include_test)
            else:
                data = get_newborn_with_low_birth_weight_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_newborn_with_low_birth_weight_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_newborn_with_low_birth_weight_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_early_initiation_breastfeeding_data(domain, config, loc_level, location, include_test)
            else:
                data = get_early_initiation_breastfeeding_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_early_initiation_breastfeeding_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_early_initiation_breastfeeding_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_exclusive_breastfeeding_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_exclusive_breastfeeding_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_exclusive_breastfeeding_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_exclusive_breastfeeding_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_children_initiated_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_children_initiated_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_children_initiated_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_children_initiated_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_institutional_deliveries_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_institutional_deliveries_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_institutional_deliveries_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_institutional_deliveries_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_immunization_coverage_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_immunization_coverage_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_immunization_coverage_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_immunization_coverage_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class AWCDailyStatusView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow() - relativedelta(days=1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(now.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        if location == 'null' or location == 'undefined':
            location = None
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_awc_daily_status_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_awc_daily_status_data_map(domain, config.copy(), loc_level, include_test)
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


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_awcs_covered_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_awcs_covered_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_awcs_covered_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_awcs_covered_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_registered_household_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_registered_household_data_map(domain, config.copy(), loc_level, include_test)
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


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_enrolled_children_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_enrolled_children_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_enrolled_children_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            if 'age' in config:
                del config['age']
            data = get_enrolled_children_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_enrolled_women_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_enrolled_women_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_enrolled_women_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_enrolled_women_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_lactating_enrolled_women_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_lactating_enrolled_women_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_lactating_enrolled_women_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_lactating_enrolled_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class AdolescentGirlsView(BaseReportView):
    def get(self, request, *args, **kwargs):
        step, now, month, year, include_test, domain, current_month, prev_month, location, selected_month = \
            self.get_settings(request, *args, **kwargs)

        config = {
            'month': tuple(selected_month.timetuple())[:3],
            'aggregation_level': 1,
        }
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adolescent_girls_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_adolescent_girls_data_map(domain, config.copy(), loc_level, include_test)
                if loc_level == LocationTypes.BLOCK:
                    sector = get_adolescent_girls_sector_data(
                        domain, config, loc_level, location, include_test
                    )
                    data.update(sector)
        elif step == "chart":
            data = get_adolescent_girls_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
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


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_clean_water_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_clean_water_data_map(domain, config.copy(), loc_level, include_test)
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


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_functional_toilet_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_functional_toilet_data_map(domain, config.copy(), loc_level, include_test)
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


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_medicine_kit_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_medicine_kit_data_map(domain, config.copy(), loc_level, include_test)
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


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_infants_weight_scale_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_infants_weight_scale_data_map(domain, config.copy(), loc_level, include_test)
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


@method_decorator([login_and_domain_required], name='dispatch')
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

        data = {}
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adult_weight_scale_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_adult_weight_scale_data_map(domain, config.copy(), loc_level, include_test)
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


class ICDSBugReportView(BugReportView):
    @property
    def recipients(self):
        return [ICDS_SUPPORT_EMAIL]


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
class DishaAPIView(View):

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
        try:
            month = int(request.GET.get('month'))
            year = int(request.GET.get('year'))
        except (ValueError, TypeError):
            return JsonResponse(self.message('missing_date'), status=400)

        # Can return only one month old data if today is after 5th, otherwise
        #   can return two month's old data
        query_month = date(year, month, 1)
        today = date.today()
        current_month = today - relativedelta(months=1) if today.day <= 5 else today
        if query_month > current_month:
            return JsonResponse(self.message('invalid_month'), status=400)

        state_name = self.request.GET.get('state_name')
        if state_name not in self.valid_state_names:
            return JsonResponse(self.message('invalid_state'), status=400)

        dump = DishaDump(state_name, query_month)
        return dump.get_export_as_http_response(request)

    @property
    @icds_quickcache([])
    def valid_state_names(self):
        return list(AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE, state_is_test=0).values_list('state_name', flat=True))


@location_safe
@method_decorator([api_auth, csrf_exempt, toggles.ICDS_NIC_INDICATOR_API.required_decorator()], name='dispatch')
class NICIndicatorAPIView(View):

    def message(self, message_name):
        state_names = ", ".join(self.valid_states.keys())
        error_messages = {
            "missing_date": "Please specify valid month and year",
            "invalid_month": "Please specify a month that's older than or same as current month",
            "invalid_state": "Please specify one of {} as state_name".format(state_names),
            "unknown_error": "Unknown Error occured",
            "no_data": "Data does not exists"
        }

        error_message_template = """
            <?xml version="1.0" encoding="UTF-8"?>
            <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2001/12/soap-envelope"
            SOAP-ENV:encodingStyle="http://www.w3.org/2001/12/soap-encoding">
               <SOAP-ENV:Header />
               <SOAP-ENV:Body>
                    <SOAP-ENV:Fault>
                        <message>
                            {}
                        </message>
                    </SOAP-ENV:Fault>
               </SOAP-ENV:Body>
            </SOAP-ENV:Envelope>
            """
        return error_message_template.format(error_messages[message_name]).strip()

    def get_data(self, post_body):
        xml_data = etree.fromstring(post_body.strip())
        nic_indicators_request = {
            'month': xml_data.xpath('//month')[0].text if xml_data.xpath('//month') else None,
            'year': xml_data.xpath('//year')[0].text if xml_data.xpath('//year') else None,
            'state_name': xml_data.xpath('//state_name')[0].text if xml_data.xpath('//state_name') else None,

        }
        return nic_indicators_request

    def post(self, request, *args, **kwargs):

        nic_indicators_request = self.get_data(request.body)
        try:
            month = int(nic_indicators_request.get('month'))
            year = int(nic_indicators_request.get('year'))
        except (ValueError, TypeError):
            return HttpResponse(self.message('missing_date'), content_type='text/xml', status=400)

        query_month = date(year, month, 1)
        today = date.today()
        current_month = today - relativedelta(months=1)
        if query_month > current_month:
            return HttpResponse(self.message('invalid_month'), content_type='text/xml', status=400)

        state_name = nic_indicators_request.get('state_name')

        if state_name not in self.valid_states:
            return HttpResponse(self.message('invalid_state'), content_type='text/xml', status=400)

        try:
            state_id = self.valid_states[state_name]
            data = get_inc_indicator_api_data(state_id, month_formatter(query_month))
            return HttpResponse(data, content_type='text/xml')
        except NICIndicatorsView.DoesNotExist:
            return HttpResponse(self.message('no_data'), content_type='text/xml', status=500)
        except AttributeError:
            return HttpResponse(self.message('unknown_error'), content_type='text/xml', status=500)

    @property
    @icds_quickcache([])
    def valid_states(self):
        states = AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE,
                                            state_is_test=0).values_list('state_name', 'state_id')
        return {state[0]: state[1] for state in states}


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class CasDataExport(View):
    def post(self, request, *args, **kwargs):
        data_type = int(request.POST.get('indicator', None))
        state_id = request.POST.get('location', None)
        month = int(request.POST.get('month', None))
        year = int(request.POST.get('year', None))
        selected_date = date(year, month, 1).strftime('%Y-%m-%d')

        sync, _ = get_cas_data_blob_file(data_type, state_id, selected_date)
        if not sync:
            return JsonResponse({"message": "Export not exists."})
        else:
            params = dict(
                indicator=data_type,
                location=state_id,
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
        data_type = int(request.GET.get('indicator', None))
        state_id = request.GET.get('location', None)
        month = int(request.GET.get('month', None))
        year = int(request.GET.get('year', None))
        selected_date = date(year, month, 1).strftime('%Y-%m-%d')

        sync, blob_id = get_cas_data_blob_file(data_type, state_id, selected_date)

        try:
            return export_response(sync.get_file_from_blobdb(), 'unzipped-csv', blob_id)
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
        type_code = self.get_type_code(data_type)

        sync, blob_id = get_cas_data_blob_file(type_code, state_id, selected_date)

        try:
            return export_response(sync.get_file_from_blobdb(), 'unzipped-csv', blob_id)
        except NotFound:
            return JsonResponse(self.message('not_available'), status=400)

    @property
    @icds_quickcache([])
    def valid_state_names(self):
        return list(AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE, state_is_test=0).values_list('state_name', flat=True))

    @property
    def valid_types(self):
        return ('woman', 'child', 'awc')

    def get_type_code(self, data_type):
        type_map = {
            "child": 1,
            "woman": 2,
            "awc": 3
        }
        return type_map[data_type]
