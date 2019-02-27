from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import F, Func, Q
from django.db.models.functions import ExtractYear
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView, View

from corehq.apps.domain.decorators import login_and_domain_required, require_superuser_or_contractor
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.hqwebapp.views import no_permissions
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe

from custom.aaa.const import COLORS, INDICATOR_LIST, NUMERIC, PERCENT
from custom.aaa.models import Woman
from custom.aaa.tasks import (
    update_agg_awc_table,
    update_agg_village_table,
    update_ccs_record_table,
    update_child_table,
    update_child_history_table,
    update_woman_table,
    update_woman_history_table,
)
from custom.aaa.utils import build_location_filters, get_location_model_for_ministry

from dimagi.utils.dates import force_to_date


class ReachDashboardView(TemplateView):
    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def couch_user(self):
        return self.request.couch_user

    @property
    def user_ministry(self):
        return self.couch_user.user_data.get('ministry')

    def dispatch(self, *args, **kwargs):
        if (not self.couch_user.is_web_user()
                and (self.user_ministry is None or self.user_ministry == '')):
            return no_permissions(self.request)

        return super(ReachDashboardView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs['domain'] = self.domain

        kwargs['is_web_user'] = self.couch_user.is_web_user()
        kwargs['user_role_type'] = self.user_ministry

        if (not kwargs['is_web_user']
                and (kwargs['user_role_type'] is None or kwargs['user_role_type'] == '')):
            return no_permissions(self.request)

        user_location = self.couch_user.get_sql_locations(self.domain).first()
        kwargs['user_location_id'] = user_location.location_id if user_location else None
        user_locations_with_parents = SQLLocation.objects.get_queryset_ancestors(
            user_location, include_self=True
        ).distinct() if user_location else []
        parent_ids = [loc.location_id for loc in user_locations_with_parents]
        kwargs['user_location_ids'] = parent_ids
        kwargs['is_details'] = False
        return super(ReachDashboardView, self).get_context_data(**kwargs)


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class ProgramOverviewReport(ReachDashboardView):
    template_name = 'aaa/reports/program_overview.html'


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class ProgramOverviewReportAPI(View):
    def post(self, request, *args, **kwargs):
        selected_month = int(self.request.POST.get('selectedMonth'))
        selected_year = int(self.request.POST.get('selectedYear'))
        selected_location = self.request.POST.get('selectedLocation')
        selected_date = date(selected_year, selected_month, 1)
        prev_month = date(selected_year, selected_month, 1) - relativedelta(months=1)

        location_filters = build_location_filters(selected_location)
        data = get_location_model_for_ministry(self.user_ministry).objects.filter(
            (Q(month=selected_date) | Q(month=prev_month)),
            domain=self.request.domain,
            **location_filters
        ).order_by('month').values()

        vals = {
            val['month']: val
            for val in data
        }
        data = vals.get(selected_date, {})
        prev_month_data = vals.get(prev_month, {})

        return JsonResponse(data={'data': [
            [
                {
                    'indicator': INDICATOR_LIST['registered_eligible_couples'],
                    'format': NUMERIC,
                    'color': COLORS['violet'],
                    'value': data.get('registered_eligible_couples', 0),
                    'past_month_value': prev_month_data.get('registered_eligible_couples', 0)
                },
                {
                    'indicator': INDICATOR_LIST['registered_pregnancies'],
                    'format': NUMERIC,
                    'color': COLORS['blue'],
                    'value': data.get('registered_pregnancies', 0),
                    'past_month_value': prev_month_data.get('registered_pregnancies', 0)
                },
                {
                    'indicator': INDICATOR_LIST['registered_children'],
                    'format': NUMERIC,
                    'color': COLORS['orange'],
                    'value': data.get('registered_children', 0),
                    'past_month_value': prev_month_data.get('registered_children', 0)
                }
            ],
            [
                {
                    'indicator': INDICATOR_LIST['couples_family_planning'],
                    'format': PERCENT,
                    'color': COLORS['aqua'],
                    'value': data.get('eligible_couples_using_fp_method', 0),
                    'total': data.get('registered_eligible_couples', 0),
                    'past_month_value': prev_month_data.get('eligible_couples_using_fp_method', 0),
                },
                {
                    'indicator': INDICATOR_LIST['high_risk_pregnancies'],
                    'format': PERCENT,
                    'color': COLORS['darkorange'],
                    'value': data.get('high_risk_pregnancies', 0),
                    'total': data.get('registered_pregnancies', 0),
                    'past_month_value': prev_month_data.get('high_risk_pregnancies', 0),
                },
                {
                    'indicator': INDICATOR_LIST['institutional_deliveries'],
                    'format': PERCENT,
                    'color': COLORS['mediumblue'],
                    'value': data.get('institutional_deliveries', 0),
                    'total': data.get('total_deliveries', 0),
                    'past_month_value': prev_month_data.get('institutional_deliveries', 0),
                }
            ]
        ]})


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class UnifiedBeneficiaryReport(ReachDashboardView):
    template_name = 'aaa/reports/unified_beneficiary.html'


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class UnifiedBeneficiaryReportAPI(View):
    def post(self, request, *args, **kwargs):
        # TODO add query to database
        # Prepared to the ajax pagination, remember that we need to return number of rows = length
        # start - selected page on the UI (if first page selected then start = 0)
        # sortColumn - name of the sorting column
        # sortColumnDir - asc or desc

        selected_month = int(self.request.POST.get('selectedMonth'))
        selected_year = int(self.request.POST.get('selectedYear'))
        selected_date = date(selected_year, selected_month, 1)
        selected_location = self.request.POST.get('selectedLocation')
        beneficiary_type = self.request.POST.get('selectedBeneficiaryType')
        draw = self.request.POST.get('draw', 0)
        length = self.request.POST.get('length', 0)
        start = self.request.POST.get('start', 0)
        sortColumn = self.request.POST.get('sortColumn', 0)
        sortColumnDir = self.request.POST.get('sortColumnDir', 0)
        data = []
        if beneficiary_type == 'child':
             data = [
                dict(id=1, name='test 1', age='27', gender='M', lastImmunizationType=1, lastImmunizationDate='2018-03-03'),
                dict(id=2, name='test 2', age='12', gender='M', lastImmunizationType=1, lastImmunizationDate='2018-03-03'),
                dict(id=3, name='test 3', age='3', gender='M', lastImmunizationType=1, lastImmunizationDate='2018-03-03'),
                dict(id=4, name='test 4', age='5', gender='M', lastImmunizationType=1, lastImmunizationDate='2018-03-03'),
                dict(id=5, name='test 5', age='16', gender='M', lastImmunizationType=1, lastImmunizationDate='2018-03-03'),
                dict(id=6, name='test 6', age='19', gender='M', lastImmunizationType=1, lastImmunizationDate='2018-03-03'),
            ]
        elif beneficiary_type == 'eligible_couple':
            data = (
                Woman.objects
                .annotate(
                    age=ExtractYear(Func(F('dob'), function='age')),
                )
                .filter(
                    # should filter for location
                    domain=request.domain,
                    age__range=(19, 49),
                    marital_status='married',
                )
                .exclude(migration_status='yes')
                .extra(
                    select={
                        'currentFamilyPlanningMethod': 0,
                        'adoptionDateOfFamilyPlaning': '2018-03-01',
                        'id': 'person_case_id',
                    },
                    where=["NOT daterange(%s, %s) && any(pregnant_ranges)"],
                    params=[selected_date, selected_date + relativedelta(months=1)]
                )
                .values(
                    'id', 'name', 'age',
                    'currentFamilyPlanningMethod', 'adoptionDateOfFamilyPlaning')
            )[:10]
            data = list(data)
        elif beneficiary_type == 'pregnant_women':
            data = [
                dict(id=1, name='test 1', age='22', pregMonth='2018-03-03', highRiskPregnancy=1, noOfAncCheckUps=9),
                dict(id=2, name='test 2', age='32', pregMonth='2018-03-03', highRiskPregnancy=0, noOfAncCheckUps=9),
                dict(id=3, name='test 3', age='17', pregMonth='2018-03-03', highRiskPregnancy=1, noOfAncCheckUps=9),
                dict(id=4, name='test 4', age='56', pregMonth='2018-03-03', highRiskPregnancy=1, noOfAncCheckUps=9),
                dict(id=5, name='test 5', age='48', pregMonth='2018-03-03', highRiskPregnancy=0, noOfAncCheckUps=9),
                dict(id=6, name='test 6', age='19', pregMonth='2018-03-03', highRiskPregnancy=1, noOfAncCheckUps=9),
            ]
        return JsonResponse(data={
            'rows': data,
            'draw': draw,
            'recordsTotal': len(data),
            'recordsFiltered': len(data),
        })


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class LocationFilterAPI(View):
    def post(self, request, *args, **kwargs):
        selected_location = self.request.POST.get('selectedParentId', None)
        location_type = self.request.POST.get('locationType', None)
        domain = self.kwargs['domain']
        locations = SQLLocation.objects.filter(
            domain=domain,
            location_type__code=location_type
        )
        if selected_location:
            locations.filter(parent__location_id=selected_location)

        return JsonResponse(data={'data': [
            dict(
                id=loc.location_id,
                name=loc.name,
                parent_id=loc.parent.location_id if loc.parent else None
            ) for loc in locations]
        })


@method_decorator([login_and_domain_required, require_superuser_or_contractor], name='dispatch')
class AggregationScriptPage(BaseDomainView):
    page_title = 'Aggregation Script'
    urlname = 'aggregation_script_page'
    template_name = 'icds_reports/aggregation_script.html'

    @use_daterangepicker
    def dispatch(self, *args, **kwargs):
        if settings.SERVER_ENVIRONMENT != 'softlayer':
            return HttpResponse("This page is only available for QA and not available for production instances.")

        couch_user = self.request.couch_user
        if couch_user.is_domain_admin(self.domain):
            return super(AggregationScriptPage, self).dispatch(*args, **kwargs)

        raise PermissionDenied()

    def section_url(self):
        return

    def post(self, request, *args, **kwargs):
        date_param = self.request.POST.get('date')
        if not date_param:
            messages.error(request, 'Date is required')
            return redirect(self.urlname, domain=self.domain)
        date = force_to_date(date_param)
        update_child_table(self.domain)
        update_child_history_table(self.domain)
        update_ccs_record_table(self.domain)
        update_woman_table(self.domain)
        update_woman_history_table(self.domain)
        update_agg_awc_table(self.domain, date)
        update_agg_village_table(self.domain, date)
        messages.success(request, 'Aggregation task has run.')
        return redirect(self.urlname, domain=self.domain)


@method_decorator([login_and_domain_required], name='dispatch')
class UnifiedBeneficiaryDetailsReport(ReachDashboardView):
    template_name = 'aaa/reports/unified_beneficiary_details.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['is_details'] = True
        context['beneficiary_id'] = kwargs.get('beneficiary_id')
        context['selected_type'] = kwargs.get('details_type')
        context['selected_month'] = int(request.GET.get('month'))
        context['selected_year'] = int(request.GET.get('year'))
        context['beneficiary_location_names'] = [
            'Haryana',
            'Ambala',
            'Shahzadpur',
            'PHC Shahzadpur',
            'SC shahzadpur',
            'Rasidpur'
        ]
        return self.render_to_response(context)


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class UnifiedBeneficiaryDetailsReportAPI(View):
    def post(self, request, *args, **kwargs):
        selected_month = int(self.request.POST.get('selectedMonth', 0))
        selected_year = int(self.request.POST.get('selectedYear', 0))
        section = self.request.POST.get('section', '')
        sub_section = self.request.POST.get('subsection', '')
        beneficiary_id = self.request.POST.get('beneficiaryId', '')
        data = {}
        if section == 'child':
            data = {}
        elif section == 'pregnant_women':
            data = {}
        elif section == 'eligible_couples':
            if sub_section == 'person_details':
                person = dict(
                    name='Reena Kumar',
                    gender='Female',
                    status='Pregnant Woman',
                    dob=date(1991, 5, 11),
                    marriedAt=25,
                    aadhaarNo='Yes'
                )
                husband = dict(
                    name='Raju Kumar',
                    gender='Female',
                    dob=date(1991, 5, 11),
                    marriedAt=26,
                    aadhaarNo='Yes'
                )
                other = dict(
                    address='J-142, Saket, New Delhi, Delhi',
                    subcentre='Rasidpur',
                    village='Rasidpur',
                    anganwadiCentre='Aspataal Ward',
                    phone='844-860-4774',
                    religion='Hinduk',
                    caste='Sudra',
                    bplOrApl='BPL',

                )
                data = dict(
                    person=person,
                    husband=husband,
                    other=other,
                )
            elif sub_section == 'child_details':
                children = [
                    dict(id=1, name='Ritu Kummar', age=8),
                    dict(id=2, name='Rahul Kumar', age=6),
                    dict(id=3, name='Jhanvi Kumar', age=3),
                    dict(id=4, name='Rohit Kumar', age=1),
                ]
                data = dict(
                    children=children
                )
            elif sub_section == 'eligible_couple_details':
                data = dict(
                    maleChildrenBorn=3,
                    femaleChildrenBorn=2,
                    maleChildrenAlive=2,
                    femaleChildrenAlive=2,
                    familyPlaningMethod='OC pills',
                    familyPlanningMethodDate='2018-07-14',
                    ashaVisit='2019-01-11',
                    previousFamilyPlanningMethod='Condom',
                    preferredFamilyPlaningMethod='Male sterilization'
                )
        return JsonResponse(data=data)
