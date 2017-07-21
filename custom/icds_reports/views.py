import requests

from datetime import datetime, date

from dateutil.relativedelta import relativedelta
from django.db.models.query_utils import Q
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, user_can_access_location_id
from corehq.apps.locations.util import location_hierarchy_config
from custom.icds_reports.const import LocationTypes
from custom.icds_reports.filters import CasteFilter, MinorityFilter, DisabledFilter, \
    ResidentFilter, MaternalStatusFilter, ChildAgeFilter, THRBeneficiaryType, ICDSMonthFilter, \
    TableauLocationFilter, ICDSYearFilter

from custom.icds_reports.sqldata import ChildrenExport, ProgressReport, PregnantWomenExport, \
    DemographicsExport, SystemUsageExport, AWCInfrastructureExport
from custom.icds_reports.utils import get_maternal_child_data, get_cas_reach_data, \
    get_demographics_data, get_awc_infrastructure_data, get_awc_opened_data, \
    get_prevalence_of_undernutrition_data_map, get_prevalence_of_undernutrition_data_chart, \
    get_awc_reports_system_usage, get_awc_reports_pse, get_awc_reports_maternal_child, \
    get_awc_report_demographics, get_location_filter, get_awc_report_beneficiary, get_beneficiary_details, \
    get_prevalence_of_undernutrition_sector_data, get_prevalence_of_severe_sector_data, \
    get_prevalence_of_severe_data_map, get_prevalence_of_severe_data_chart, \
    get_prevalence_of_stunning_sector_data, get_prevalence_of_stunning_data_map, \
    get_prevalence_of_stunning_data_chart
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
        day = int(self.request.GET.get('day', now.day))

        test_date = datetime(year, month, day)

        yesterday = (test_date - relativedelta(days=1)).date()
        current_month = datetime(year, month, 1)
        prev_month = current_month - relativedelta(months=1)

        if step == 'system_usage' or step == 'demographics':
            config = {
                'aggregation_level': 1
            }
        else:
            config = {
                'month': tuple(current_month.timetuple())[:3],
                'prev_month': tuple(prev_month.timetuple())[:3],
                'aggregation_level': 1
            }

        location = request.GET.get('location_id', '')
        get_location_filter(location, self.kwargs['domain'], config)

        data = {}
        if step == 'maternal_child':
            data = get_maternal_child_data(config)
        elif step == 'icds_cas_reach':
            data = get_cas_reach_data(
                tuple(yesterday.timetuple())[:3],
                config
            )
        elif step == 'demographics':
            data = get_demographics_data(
                tuple(yesterday.timetuple())[:3],
                config
            )
        elif step == 'awc_infrastructure':
            data = get_awc_infrastructure_data(config)
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
            data = get_awc_opened_data(config)
        elif step == "chart":
            pass
        return JsonResponse(data=data)


@method_decorator([login_and_domain_required], name='dispatch')
class PrevalenceOfUndernutritionView(View):

    def get(self, request, *args, **kwargs):
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1l,
        }
        location = request.GET.get('location_id', '')
        loc_level = get_location_filter(location, self.kwargs['domain'], config)

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_undernutrition_sector_data(config, loc_level)
            else:
                data = get_prevalence_of_undernutrition_data_map(config, loc_level)
        elif step == "chart":
            data = get_prevalence_of_undernutrition_data_chart(config, loc_level)

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
                'location_type': location.location_type.code
            })

        parent_id = request.GET.get('parent_id')
        locations = SQLLocation.objects.accessible_to_user(self.kwargs['domain'], self.request.couch_user)
        if not parent_id:
            locations = SQLLocation.objects.filter(domain=self.kwargs['domain'], parent_id__isnull=True)
        else:
            locations = locations.filter(parent__location_id=parent_id)
        return JsonResponse(data={
            'locations': [
                {'location_id': loc.location_id, 'name': loc.name, 'parent_id': parent_id}
                for loc in locations
            ]
        })


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class LocationAncestorsView(View):
    def get(self, request, *args, **kwargs):
        location_id = request.GET.get('location_id')
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
                    'parent_id': location.parent.location_id if location.parent else None
                }
                for location in set(list(locations) + list(parents))
            ],
            'selected_location': {
                'location_type': selected_location.location_type_name,
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

        now = datetime.utcnow()
        month_param = int(request.GET.get('month', now.month))
        year_param = int(request.GET.get('year', now.year))
        month = datetime(year_param, month_param, 1)
        prev_month = month - relativedelta(months=1)
        two_before = month - relativedelta(months=2)
        location = request.GET.get('location_id', None)
        aggregation_level = 5

        config = {
            'aggregation_level': aggregation_level,
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

        data = []
        if step == 'system_usage':
            data = get_awc_reports_system_usage(
                config,
                tuple(month.timetuple())[:3],
                tuple(prev_month.timetuple())[:3],
                tuple(two_before.timetuple())[:3],
                'aggregation_level'
            )
        elif step == 'pse':
            data = get_awc_reports_pse(
                config,
                tuple(month.timetuple())[:3],
                tuple(two_before.timetuple())[:3],
                self.kwargs.get('domain')
            )
        elif step == 'maternal_child':
            data = get_awc_reports_maternal_child(
                config,
                tuple(month.timetuple())[:3],
                tuple(prev_month.timetuple())[:3]
            )
        elif step == 'demographics':
            data = get_awc_report_demographics(
                config,
                tuple(month.timetuple())[:3]
            )
        elif step == 'beneficiary':
            data = get_awc_report_beneficiary(
                config['awc_id'],
                tuple(month.timetuple())[:3],
                tuple(two_before.timetuple())[:3],
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

        export_format = request.POST.get('format')
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        aggregation_level = int(request.POST.get('aggregation_level'))
        indicator = int(request.POST.get('indicator'))

        config = {
            'aggregation_level': aggregation_level
        }

        if month and year:
            config.update({
                'month': date(year, month, 1),
            })

        location = request.POST.get('location_id', '')

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

        if indicator == 1:
            return ChildrenExport(config=config, loc_level=aggregation_level).to_export(export_format, location)
        elif indicator == 2:
            return PregnantWomenExport(config=config, loc_level=aggregation_level).to_export(export_format, location)
        elif indicator == 3:
            return DemographicsExport(config=config, loc_level=aggregation_level).to_export(export_format, location)
        elif indicator == 4:
            return SystemUsageExport(config=config, loc_level=aggregation_level).to_export(export_format, location)
        elif indicator == 5:
            return AWCInfrastructureExport(
                config=config, loc_level=aggregation_level
            ).to_export(export_format, location)


@method_decorator([login_and_domain_required], name='dispatch')
class ProgressReportView(View):
    def get(self, request, *args, **kwargs):

        now = datetime.utcnow()
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        location = request.GET.get('location_id', None)
        aggregation_level = 1

        this_month = datetime(year, month, 1).date()
        two_before = this_month - relativedelta(months=2)

        config = {
            'aggregation_level': aggregation_level,
            'month': this_month,
            'two_before': two_before
        }

        loc_level = get_location_filter(location, self.kwargs['domain'], config)

        data = ProgressReport(config=config, loc_level=loc_level).get_data()
        return JsonResponse(data=data)


@method_decorator([login_and_domain_required], name='dispatch')
class PrevalenceOfSevereView(View):

    def get(self, request, *args, **kwargs):
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1l,
        }
        location = request.GET.get('location_id', '')
        loc_level = get_location_filter(location, self.kwargs['domain'], config)

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_severe_sector_data(config, loc_level)
            else:
                data = get_prevalence_of_severe_data_map(config, loc_level)
        elif step == "chart":
            data = get_prevalence_of_severe_data_chart(config, loc_level)

        return JsonResponse(data={
            'report_data': data,
        })


@method_decorator([login_and_domain_required], name='dispatch')
class PrevalenceOfStunningView(View):

    def get(self, request, *args, **kwargs):
        step = kwargs.get('step')
        now = datetime.utcnow()
        month = int(self.request.GET.get('month', now.month))
        year = int(self.request.GET.get('year', now.year))
        test_date = datetime(year, month, 1)

        config = {
            'month': tuple(test_date.timetuple())[:3],
            'aggregation_level': 1l,
        }
        location = request.GET.get('location_id', '')
        loc_level = get_location_filter(location, self.kwargs['domain'], config)

        data = []
        if step == "map":
            if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
                data = get_prevalence_of_stunning_sector_data(config, loc_level)
            else:
                data = get_prevalence_of_stunning_data_map(config, loc_level)
        elif step == "chart":
            data = get_prevalence_of_stunning_data_chart(config, loc_level)

        return JsonResponse(data={
            'report_data': data,
        })
