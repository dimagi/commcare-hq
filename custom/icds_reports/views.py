from __future__ import absolute_import

from __future__ import unicode_literals

from collections import OrderedDict
from wsgiref.util import FileWrapper

import requests

from datetime import datetime, date
from memoized import memoized
from celery.result import AsyncResult
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models.query_utils import Q
from django.http.response import JsonResponse, HttpResponseBadRequest, HttpResponse, StreamingHttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView, RedirectView
from django.utils.translation import ugettext as _, ugettext_lazy
from django.conf import settings

from corehq import toggles
from corehq.apps.cloudcare.utils import webapps_module
from corehq.apps.domain.decorators import login_and_domain_required, api_auth
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.views import BugReportView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, user_can_access_location_id
from corehq.apps.locations.util import location_hierarchy_config
from corehq.apps.hqwebapp.decorators import (
    use_daterangepicker,
    use_select2,
)
from corehq.apps.translations.views import ConvertTranslations, BaseTranslationsView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import UserRole, Permissions
from corehq.blobs.exceptions import NotFound
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.util.files import safe_filename_header
from custom.icds.const import AWC_LOCATION_TYPE_CODE
from custom.icds.tasks import (
    push_translation_files_to_transifex,
    pull_translation_files_from_transifex,
    delete_resources_on_transifex,
)
from custom.icds.translations.integrations.exceptions import ResourceMissing
from custom.icds.translations.integrations.transifex import Transifex
from custom.icds_reports.const import LocationTypes, BHD_ROLE, ICDS_SUPPORT_EMAIL, CHILDREN_EXPORT, \
    PREGNANT_WOMEN_EXPORT, DEMOGRAPHICS_EXPORT, SYSTEM_USAGE_EXPORT, AWC_INFRASTRUCTURE_EXPORT,\
    BENEFICIARY_LIST_EXPORT, ISSNIP_MONTHLY_REGISTER_PDF
from custom.icds_reports.forms import AppTranslationsForm
from custom.icds_reports.models.helper import IcdsFile

from custom.icds_reports.reports.adhaar import get_adhaar_data_chart, get_adhaar_data_map, get_adhaar_sector_data
from custom.icds_reports.reports.adolescent_girls import get_adolescent_girls_data_map, \
    get_adolescent_girls_sector_data, get_adolescent_girls_data_chart
from custom.icds_reports.reports.adult_weight_scale import get_adult_weight_scale_data_chart, \
    get_adult_weight_scale_data_map, get_adult_weight_scale_sector_data
from custom.icds_reports.reports.awc_daily_status import get_awc_daily_status_data_chart,\
    get_awc_daily_status_data_map, get_awc_daily_status_sector_data
from custom.icds_reports.reports.awc_infrastracture import get_awc_infrastructure_data
from custom.icds_reports.reports.awc_reports import get_awc_report_beneficiary, get_awc_report_demographics,\
    get_awc_reports_maternal_child, get_awc_reports_pse, get_awc_reports_system_usage, get_beneficiary_details, \
    get_awc_report_infrastructure
from custom.icds_reports.reports.awcs_covered import get_awcs_covered_data_map, get_awcs_covered_sector_data, \
    get_awcs_covered_data_chart
from custom.icds_reports.reports.cas_reach_data import get_cas_reach_data
from custom.icds_reports.reports.children_initiated_data import get_children_initiated_data_chart, \
    get_children_initiated_data_map, get_children_initiated_sector_data
from custom.icds_reports.reports.clean_water import get_clean_water_data_map, get_clean_water_data_chart, \
    get_clean_water_sector_data
from custom.icds_reports.reports.demographics_data import get_demographics_data
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
from custom.icds_reports.reports.maternal_child import get_maternal_child_data
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
from custom.icds_reports.tasks import move_ucr_data_into_aggregation_tables, \
    prepare_issnip_monthly_register_reports, prepare_excel_reports
from custom.icds_reports.utils import get_age_filter, get_location_filter, \
    get_latest_issue_tracker_build_id, get_location_level, icds_pre_release_features, \
    current_month_stunting_column, current_month_wasting_column
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.dates import force_to_date
from . import const
from .exceptions import TableauTokenException
from couchexport.shortcuts import export_response
from couchexport.export import Format


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


class IcdsDynamicTemplateView(TemplateView):

    def get_template_names(self):
        return ['icds_reports/icds_app/%s.html' % self.kwargs['template']]


class BaseReportView(View):
    def get_settings(self, request, *args, **kwargs):
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))

        if (now.day == 1 or now.day == 2) and now.month == month and now.year == year:
            month = (now - relativedelta(months=1)).month
            year = now.year

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

        data = {}
        if step == 'maternal_child':
            data = get_maternal_child_data(
                domain, config, include_test, icds_pre_release_features(self.request.couch_user)
            )
        elif step == 'icds_cas_reach':
            data = get_cas_reach_data(
                domain,
                tuple(now.date().timetuple())[:3],
                config,
                include_test
            )
        elif step == 'demographics':
            data = get_demographics_data(
                domain,
                tuple(now.date().timetuple())[:3],
                config,
                include_test,
                beta=icds_pre_release_features(request.couch_user)
            )
        elif step == 'awc_infrastructure':
            data = get_awc_infrastructure_data(domain, config, include_test)
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


@location_safe
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
            if 'awc_id' in config:
                start = int(request.GET.get('start', 0))
                length = int(request.GET.get('length', 10))
                draw = int(request.GET.get('draw', 0))
                icds_features_flag = icds_pre_release_features(self.request.couch_user)
                order_by_number_column = request.GET.get('order[0][column]')
                order_by_name_column = request.GET.get('columns[%s][data]' % order_by_number_column, 'person_name')
                order_dir = request.GET.get('order[0][dir]', 'asc')
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
                    config['awc_id'],
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
        return JsonResponse(data=data)


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
        if indicator in (CHILDREN_EXPORT, PREGNANT_WOMEN_EXPORT, DEMOGRAPHICS_EXPORT, SYSTEM_USAGE_EXPORT,
                         AWC_INFRASTRUCTURE_EXPORT, BENEFICIARY_LIST_EXPORT):
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


@method_decorator([login_and_domain_required], name='dispatch')
class DownloadExportReport(View):
    def get(self, request, *args, **kwargs):
        uuid = self.request.GET.get('uuid', None)
        file_format = self.request.GET.get('file_format', 'xlsx')
        content_type = Format.from_format(file_format)
        data_type = self.request.GET.get('data_type', 'beneficiary_list')
        icds_file = IcdsFile.objects.get(blob_id=uuid, data_type=data_type)
        response = HttpResponse(
            icds_file.get_file_from_blobdb().read(),
            content_type=content_type.mimetype
        )
        response['Content-Disposition'] = safe_filename_header(data_type, content_type.extension)
        return response


@method_decorator([login_and_domain_required], name='dispatch')
class DownloadPDFReport(View):
    def get(self, request, *args, **kwargs):
        uuid = self.request.GET.get('uuid', None)
        format = self.request.GET.get('format', None)
        icds_file = IcdsFile.objects.get(blob_id=uuid, data_type='issnip_monthly')
        if format == 'one':
            response = HttpResponse(icds_file.get_file_from_blobdb().read(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="ICDS_CAS_monthly_register_cumulative.pdf"'
            return response
        else:
            response = HttpResponse(icds_file.get_file_from_blobdb().read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="ICDS_CAS_monthly_register.zip"'
            return response


@method_decorator([login_and_domain_required], name='dispatch')
class CheckExportReportStatus(View):
    def get(self, request, *args, **kwargs):
        task_id = self.request.GET.get('task_id', None)
        res = AsyncResult(task_id)
        status = res.ready()

        if status:
            return JsonResponse(
                {
                    'task_ready': status,
                    'task_result': res.result
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
@method_decorator([toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.required_decorator()], name='dispatch')
class AppTranslations(BaseTranslationsView):
    page_title = ugettext_lazy('App Translations')
    urlname = 'app_translations'
    template_name = 'icds_reports/icds_app/app_translations.html'
    section_name = ugettext_lazy("Translations")

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(AppTranslations, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def translations_form(self):
        if self.request.POST:
            return AppTranslationsForm(self.domain, self.request.POST)
        else:
            return AppTranslationsForm(self.domain)

    @property
    def page_context(self):
        context = super(AppTranslations, self).page_context
        if context['transifex_details_available']:
            context['translations_form'] = self.translations_form
        return context

    def section_url(self):
        return reverse(ConvertTranslations.urlname, args=self.args, kwargs=self.kwargs)

    def transifex(self, domain, form_data):
        transifex_project_slug = form_data.get('transifex_project_slug')
        source_language_code = form_data.get('target_lang') or form_data.get('source_lang')
        return Transifex(domain, form_data['app_id'], source_language_code, transifex_project_slug,
                         form_data['version'],
                         use_version_postfix='yes' in form_data['use_version_postfix'],
                         update_resource='yes' in form_data['update_resource'])

    def perform_push_request(self, request, form_data):
        if form_data['target_lang']:
            if not self.ensure_resources_present(request):
                return False
        push_translation_files_to_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to submit files for translations'))
        return True

    def resources_translated(self, request):
        resource_pending_translations = (self._transifex.
                                         resources_pending_translations(break_if_true=True))
        if resource_pending_translations:
            messages.error(
                request,
                _("Resources yet to be completely translated, for ex: {}".format(
                    resource_pending_translations)))
            return False
        return True

    def ensure_resources_present(self, request):
        if not self._transifex.resource_slugs:
            messages.error(request, _('Resources not found for this project and version.'))
            return False
        return True

    def perform_pull_request(self, request, form_data):
        if not self.ensure_resources_present(request):
            return False
        if form_data['perform_translated_check']:
            if not self.resources_translated(request):
                return False
        if form_data['lock_translations']:
            if self._transifex.resources_pending_translations(break_if_true=True, all_langs=True):
                messages.error(request, _('Resources yet to be completely translated for all languages. '
                                          'Hence, the request for locking resources can not be performed.'))
                return False
        pull_translation_files_from_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to pull for translations. '
                                    'You should receive an email shortly'))
        return True

    def perform_delete_request(self, request, form_data):
        if not self.ensure_resources_present(request):
            return False
        if self._transifex.resources_pending_translations(break_if_true=True, all_langs=True):
            messages.error(request, _('Resources yet to be completely translated for all languages. '
                                      'Hence, the request for deleting resources can not be performed.'))
            return False
        delete_resources_on_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to delete resources.'))
        return True

    def perform_request(self, request, form_data):
        self._transifex = self.transifex(request.domain, form_data)
        if not self._transifex.source_lang_is(form_data.get('source_lang')):
            messages.error(request, _('Source lang selected not available for the project'))
            return False
        else:
            if form_data['action'] == 'push':
                return self.perform_push_request(request, form_data)
            elif form_data['action'] == 'pull':
                return self.perform_pull_request(request, form_data)
            elif form_data['action'] == 'delete':
                return self.perform_delete_request(request, form_data)

    def post(self, request, *args, **kwargs):
        if self.transifex_integration_enabled(request):
            form = self.translations_form
            if form.is_valid():
                form_data = form.cleaned_data
                try:
                    if self.perform_request(request, form_data):
                        return redirect(self.urlname, domain=self.domain)
                except ResourceMissing as e:
                    messages.error(request, e)
        return self.get(request, *args, **kwargs)


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
