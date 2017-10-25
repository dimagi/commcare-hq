import requests

from datetime import datetime, date

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models.query_utils import Q
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView

from corehq import toggles
from corehq.apps.cloudcare.utils import webapps_url
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, user_can_access_location_id
from corehq.apps.locations.util import location_hierarchy_config
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.users.models import Permissions, UserRole
from custom.icds_reports.const import LocationTypes, BHD_ROLE
from custom.icds_reports.filters import CasteFilter, MinorityFilter, DisabledFilter, \
    ResidentFilter, MaternalStatusFilter, ChildAgeFilter, THRBeneficiaryType, ICDSMonthFilter, \
    TableauLocationFilter, ICDSYearFilter

from custom.icds_reports.reports.adhaar import get_adhaar_data_chart, get_adhaar_data_map, get_adhaar_sector_data
from custom.icds_reports.reports.adolescent_girls import get_adolescent_girls_data_map, \
    get_adolescent_girls_sector_data, get_adolescent_girls_data_chart
from custom.icds_reports.reports.adult_weight_scale import get_adult_weight_scale_data_chart, \
    get_adult_weight_scale_data_map, get_adult_weight_scale_sector_data
from custom.icds_reports.reports.awc_daily_status import get_awc_daily_status_data_chart,\
    get_awc_daily_status_data_map, get_awc_daily_status_sector_data
from custom.icds_reports.reports.awc_infrastracture import get_awc_infrastructure_data
from custom.icds_reports.reports.awc_opened import get_awc_opened_data
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
from custom.icds_reports.reports.prevalence_of_stunting import get_prevalence_of_stunning_data_chart, \
    get_prevalence_of_stunning_data_map, get_prevalence_of_stunning_sector_data
from custom.icds_reports.reports.prevalence_of_undernutrition import get_prevalence_of_undernutrition_data_chart,\
    get_prevalence_of_undernutrition_data_map, get_prevalence_of_undernutrition_sector_data
from custom.icds_reports.reports.registered_household import get_registered_household_data_map, \
    get_registered_household_sector_data, get_registered_household_data_chart

from custom.icds_reports.sqldata import ChildrenExport, ProgressReport, PregnantWomenExport, \
    DemographicsExport, SystemUsageExport, AWCInfrastructureExport, BeneficiaryExport
from custom.icds_reports.tasks import move_ucr_data_into_aggregation_tables
from custom.icds_reports.utils import get_age_filter, get_location_filter, \
    get_latest_issue_tracker_build_id, get_location_level
from dimagi.utils.dates import force_to_date
from . import const
from .exceptions import TableauTokenException


@location_safe
@method_decorator([toggles.ICDS_REPORTS.required_decorator(), login_and_domain_required], name='dispatch')
class TableauView(TemplateView):

    template_name = 'icds_reports/tableau.html'

    filters = [
        ICDSMonthFilter,
        ICDSYearFilter,
        TableauLocationFilter,
        CasteFilter,
        MinorityFilter,
        DisabledFilter,
        ResidentFilter,
        MaternalStatusFilter,
        ChildAgeFilter,
        THRBeneficiaryType
    ]

    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def couch_user(self):
        return self.request.couch_user

    def get_context_data(self, **kwargs):
        location_type_code, user_location_id, state_id, district_id, block_id = _get_user_location(
            self.couch_user, self.domain
        )
        client_ip = self.request.META.get('X-Forwarded-For', '')
        tableau_access_url = get_tableau_trusted_url(client_ip)

        kwargs.update({
            'report_workbook': self.kwargs.get('workbook'),
            'report_worksheet': self.kwargs.get('worksheet'),
            'debug': self.request.GET.get('debug', False),
            'view_by': location_type_code,
            'view_by_value': user_location_id,
            'state_id': state_id,
            'district_id': district_id,
            'block_id': block_id,
            'tableau_access_url': tableau_access_url,
            'filters': [
                {
                    'html': view_filter(request=self.request, domain=self.domain).render(),
                    'slug': view_filter(request=self.request, domain=self.domain).slug
                }
                for view_filter in self.filters
            ]
        })
        return super(TableauView, self).get_context_data(**kwargs)


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

    def get_context_data(self, **kwargs):
        kwargs.update(self.kwargs)
        kwargs['location_hierarchy'] = location_hierarchy_config(self.domain)
        kwargs['user_location_id'] = self.couch_user.get_location_id(self.domain)

        is_commcare_user = self.couch_user.is_commcare_user()
        is_web_user_with_edit_data_permissions = (
            self.couch_user.is_web_user() and
            self.couch_user.has_permission(self.domain, Permissions.edit_data.name)
        )

        if is_commcare_user or is_web_user_with_edit_data_permissions:
            build_id = get_latest_issue_tracker_build_id()
            kwargs['report_an_issue_url'] = webapps_url(
                domain=self.domain,
                app_id=build_id,
                module_id=0,
            )
        return super(DashboardView, self).get_context_data(**kwargs)


class IcdsDynamicTemplateView(TemplateView):

    def get_template_names(self):
        return ['icds_reports/icds_app/%s.html' % self.kwargs['template']]


@method_decorator([login_and_domain_required], name='dispatch')
class ProgramSummaryView(View):

    def get(self, request, *args, **kwargs):
        step = kwargs.get('step')

        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))

        include_test = request.GET.get('include_test', False)

        domain = self.kwargs['domain']

        yesterday = (now - relativedelta(days=1)).date()
        current_month = datetime(year, month, 1)
        prev_month = current_month - relativedelta(months=1)

        config = {
            'month': tuple(current_month.timetuple())[:3],
            'prev_month': tuple(prev_month.timetuple())[:3],
            'aggregation_level': 1
        }

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, domain))

        data = {}
        if step == 'maternal_child':
            data = get_maternal_child_data(domain, config, include_test)
        elif step == 'icds_cas_reach':
            data = get_cas_reach_data(
                domain,
                tuple(yesterday.timetuple())[:3],
                config,
                include_test
            )
        elif step == 'demographics':
            data = get_demographics_data(
                domain,
                tuple(yesterday.timetuple())[:3],
                config,
                include_test
            )
        elif step == 'awc_infrastructure':
            data = get_awc_infrastructure_data(domain, config, include_test)
        return JsonResponse(data=data)


@method_decorator([login_and_domain_required], name='dispatch')
class AwcOpenedView(View):

    def get(self, request, *args, **kwargs):
        step = kwargs.get('step')

        data = {}

        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        day = int(self.request.GET.get('day', now.day))

        include_test = request.GET.get('include_test', False)

        domain = self.kwargs['domain']

        test_date = datetime(year, month, day)

        yesterday = (test_date - relativedelta(days=1)).date()
        two_days_ago = (test_date - relativedelta(days=2)).date()
        month = datetime(year, month, 1)
        prev_month = month - relativedelta(months=1)

        config = {
            'yesterday': tuple(yesterday.timetuple())[:3],
            'two_days_ago': tuple(two_days_ago.timetuple())[:3],
            'month': tuple(month.timetuple())[:3],
            'prev_month': tuple(prev_month.timetuple())[:3]
        }

        if step == "map":
            data = get_awc_opened_data(domain, config, include_test)
        return JsonResponse(data=data)


@method_decorator([login_and_domain_required], name='dispatch')
class PrevalenceOfUndernutritionView(View):

    def get(self, request, *args, **kwargs):
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        include_test = request.GET.get('include_test', False)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, domain))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_undernutrition_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_prevalence_of_undernutrition_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_prevalence_of_undernutrition_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class LocationView(View):

    def get(self, request, *args, **kwargs):
        if 'location_id' in request.GET:
            location_id = request.GET['location_id']
            if not user_can_access_location_id(self.kwargs['domain'], request.couch_user, location_id):
                return JsonResponse({})
            location = get_object_or_404(
                SQLLocation,
                domain=self.kwargs['domain'],
                location_id=location_id
            )
            return JsonResponse({
                'name': location.name,
                'location_type': location.location_type.code,
                'location_type_name': location.location_type_name
            })

        parent_id = request.GET.get('parent_id')
        name = request.GET.get('name')

        show_test = request.GET.get('include_test', False)

        locations = SQLLocation.objects.accessible_to_user(self.kwargs['domain'], self.request.couch_user)
        if not parent_id:
            locations = SQLLocation.objects.filter(domain=self.kwargs['domain'], parent_id__isnull=True)
        else:
            locations = locations.filter(parent__location_id=parent_id)

        if name:
            locations = locations.filter(name__iexact=name)

        return JsonResponse(data={
            'locations': [
                {
                    'location_id': loc.location_id,
                    'name': loc.name,
                    'parent_id': parent_id,
                    'location_type_name': loc.location_type_name,
                }
                for loc in locations if show_test or loc.metadata.get('is_test_location', 'real') != 'test'
            ]
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class LocationAncestorsView(View):
    def get(self, request, *args, **kwargs):
        location_id = request.GET.get('location_id')
        show_test = request.GET.get('include_test', False)
        selected_location = get_object_or_404(SQLLocation, location_id=location_id, domain=self.kwargs['domain'])
        parents = list(SQLLocation.objects.get_queryset_ancestors(
            self.request.couch_user.get_sql_locations(self.kwargs['domain']), include_self=True
        ).distinct()) + list(selected_location.get_ancestors())
        parent_ids = map(lambda x: x.pk, parents)
        locations = SQLLocation.objects.accessible_to_user(
            domain=self.kwargs['domain'], user=self.request.couch_user
        ).filter(
            ~Q(pk__in=parent_ids) & (Q(parent_id__in=parent_ids) | Q(parent_id__isnull=True))
        ).select_related('parent').distinct()
        return JsonResponse(data={
            'locations': [
                {
                    'location_id': location.location_id,
                    'name': location.name,
                    'parent_id': location.parent.location_id if location.parent else None,
                    'location_type_name': location.location_type_name,
                }
                for location in set(list(locations) + list(parents))
                if show_test or location.metadata.get('is_test_location', 'real') != 'test'
            ],
            'selected_location': {
                'location_type_name': selected_location.location_type_name,
                'location_id': selected_location.location_id,
                'name': selected_location.name,
                'parent_id': selected_location.parent.location_id if selected_location.parent else None
            }
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class AwcReportsView(View):
    def get(self, request, *args, **kwargs):
        step = kwargs.get('step')
        include_test = request.GET.get('include_test', False)

        now = datetime.utcnow()
        month_param = int(request.GET.get('month', now.month))
        year_param = int(request.GET.get('year', now.year))
        month = datetime(year_param, month_param, 1)
        prev_month = month - relativedelta(months=1)
        two_before = month - relativedelta(months=2)
        location = request.GET.get('location_id', None)
        aggregation_level = 5

        domain = self.kwargs['domain']

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
                tuple(month.timetuple())[:3],
                tuple(prev_month.timetuple())[:3],
                tuple(two_before.timetuple())[:3],
                'aggregation_level',
                include_test
            )
        elif step == 'pse':
            data = get_awc_reports_pse(
                config,
                tuple(month.timetuple())[:3],
                self.kwargs.get('domain'),
                include_test
            )
        elif step == 'maternal_child':
            data = get_awc_reports_maternal_child(
                domain,
                config,
                tuple(month.timetuple())[:3],
                tuple(prev_month.timetuple())[:3],
                include_test
            )
        elif step == 'demographics':
            data = get_awc_report_demographics(
                domain,
                config,
                tuple(month.timetuple())[:3],
                include_test
            )
        elif step == 'awc_infrastructure':
            data = get_awc_report_infrastructure(
                domain,
                config,
                tuple(month.timetuple())[:3],
                tuple(prev_month.timetuple())[:3],
                include_test
            )
        elif step == 'beneficiary':
            if 'awc_id' in config:
                data = get_awc_report_beneficiary(
                    domain,
                    config['awc_id'],
                    tuple(month.timetuple())[:3],
                    tuple(two_before.timetuple())[:3]
                )
        elif step == 'beneficiary_details':
            data = get_beneficiary_details(
                self.request.GET.get('case_id'),
                tuple(month.timetuple())[:3]
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
        beneficiary_config = {'domain': self.kwargs['domain']}

        if month and year:
            beneficiary_config['month'] = date(year, month, 1)
            config.update({
                'month': date(year, month, 1),
            })

        location = request.POST.get('location', '')

        if location:
            try:
                sql_location = SQLLocation.objects.get(location_id=location, domain=self.kwargs['domain'])
                locations = sql_location.get_ancestors(include_self=True)
                for loc in locations:
                    location_key = '%s_id' % loc.location_type.code
                    config.update({
                        location_key: loc.location_id,
                    })
                    if location_key == 'awc_id':
                        beneficiary_config.update({
                            location_key: loc.location_id
                        })
            except SQLLocation.DoesNotExist:
                pass

        if indicator == 1:
            return ChildrenExport(
                config=config,
                loc_level=aggregation_level,
                show_test=include_test
            ).to_export(export_format, location)
        elif indicator == 2:
            return PregnantWomenExport(
                config=config,
                loc_level=aggregation_level,
                show_test=include_test
            ).to_export(export_format, location)
        elif indicator == 3:
            return DemographicsExport(
                config=config,
                loc_level=aggregation_level,
                show_test=include_test
            ).to_export(export_format, location)
        elif indicator == 4:
            return SystemUsageExport(
                config=config,
                loc_level=aggregation_level,
                show_test=include_test
            ).to_export(export_format, location)
        elif indicator == 5:
            return AWCInfrastructureExport(
                config=config,
                loc_level=aggregation_level,
                show_test=include_test
            ).to_export(export_format, location)
        elif indicator == 6:
            return BeneficiaryExport(
                config=beneficiary_config,
                loc_level=aggregation_level,
                show_test=include_test
            ).to_export(export_format, location)


@method_decorator([login_and_domain_required], name='dispatch')
class ProgressReportView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        location = request.GET.get('location_id', None)
        aggregation_level = 1

        this_month = datetime(year, month, 1).date()
        two_before = this_month - relativedelta(months=2)

        domain = self.kwargs['domain']

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

        data = ProgressReport(config=config, loc_level=loc_level, show_test=include_test).get_data()
        return JsonResponse(data=data)


@method_decorator([login_and_domain_required], name='dispatch')
class PrevalenceOfSevereView(View):

    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        location = request.GET.get('location_id', '')

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_severe_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_prevalence_of_severe_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_prevalence_of_severe_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class PrevalenceOfStunningView(View):

    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        location = request.GET.get('location_id', '')

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_stunning_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_prevalence_of_stunning_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_prevalence_of_stunning_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class NewbornsWithLowBirthWeightView(View):

    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1l,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        location = request.GET.get('location_id', '')

        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_newborn_with_low_birth_weight_data(domain, config, loc_level, include_test)
            else:
                data = get_newborn_with_low_birth_weight_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_newborn_with_low_birth_weight_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class EarlyInitiationBreastfeeding(View):

    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_early_initiation_breastfeeding_data(domain, config, loc_level, include_test)
            else:
                data = get_early_initiation_breastfeeding_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_early_initiation_breastfeeding_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class ExclusiveBreastfeedingView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_exclusive_breastfeeding_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_exclusive_breastfeeding_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_exclusive_breastfeeding_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class ChildrenInitiatedView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_children_initiated_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_children_initiated_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_children_initiated_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class InstitutionalDeliveriesView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_institutional_deliveries_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_institutional_deliveries_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_institutional_deliveries_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class ImmunizationCoverageView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        gender = self.request.GET.get('gender', None)
        if gender:
            config.update({'gender': gender})

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_immunization_coverage_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_immunization_coverage_data_map(domain, config, loc_level, include_test)
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
        now = datetime.utcnow() - relativedelta(day=1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(now.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_awc_daily_status_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_awc_daily_status_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_awc_daily_status_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class AWCsCoveredView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_awcs_covered_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_awcs_covered_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_awcs_covered_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class RegisteredHouseholdView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_registered_household_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_registered_household_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_registered_household_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class EnrolledChildrenView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        gender = self.request.GET.get('gender', None)
        age = self.request.GET.get('age', None)
        if gender:
            config.update({'gender': gender})
        if age:
            config.update(get_age_filter(age))

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_enrolled_children_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_enrolled_children_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            if 'age' in config:
                del config['age']
            data = get_enrolled_children_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class EnrolledWomenView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }

        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_enrolled_women_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_enrolled_women_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_enrolled_women_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class LactatingEnrolledWomenView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_lactating_enrolled_women_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_lactating_enrolled_women_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_lactating_enrolled_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class AdolescentGirlsView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adolescent_girls_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_adolescent_girls_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_adolescent_girls_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class AdhaarBeneficiariesView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adhaar_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_adhaar_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_adhaar_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class CleanWaterView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)
        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_clean_water_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_clean_water_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_clean_water_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class FunctionalToiletView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_functional_toilet_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_functional_toilet_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_functional_toilet_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class MedicineKitView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_medicine_kit_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_medicine_kit_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_medicine_kit_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class InfantsWeightScaleView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_infants_weight_scale_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_infants_weight_scale_data_map(domain, config, loc_level, include_test)
        elif step == "chart":
            data = get_infants_weight_scale_data_chart(domain, config, loc_level, include_test)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class AdultWeightScaleView(View):
    def get(self, request, *args, **kwargs):
        include_test = request.GET.get('include_test', False)
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        domain = self.kwargs['domain']

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1,
        }
        location = request.GET.get('location_id', '')
        config.update(get_location_filter(location, self.kwargs['domain']))
        loc_level = get_location_level(config.get('aggregation_level'))

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_adult_weight_scale_sector_data(domain, config, loc_level, location, include_test)
            else:
                data = get_adult_weight_scale_data_map(domain, config, loc_level, include_test)
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
