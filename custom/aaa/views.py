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
from django.http.response import Http404
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
from custom.aaa.dbaccessors import ChildQueryHelper, EligibleCoupleQueryHelper, PregnantWomanQueryHelper
from custom.aaa.models import Woman, Child, CcsRecord, ChildHistory
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
    @property
    def couch_user(self):
        return self.request.couch_user

    @property
    def user_ministry(self):
        return self.couch_user.user_data.get('ministry')

    def post(self, request, *args, **kwargs):
        selected_month = int(self.request.POST.get('selectedMonth'))
        selected_year = int(self.request.POST.get('selectedYear'))
        selected_location = self.request.POST.get('selectedLocation')
        selected_date = date(selected_year, selected_month, 1)
        selected_ministry = self.request.POST.get('selectedMinistry')
        prev_month = date(selected_year, selected_month, 1) - relativedelta(months=1)

        location_filters = build_location_filters(selected_location, selected_ministry)
        data = get_location_model_for_ministry(selected_ministry).objects.filter(
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
        selected_month = int(self.request.POST.get('selectedMonth'))
        selected_year = int(self.request.POST.get('selectedYear'))
        selected_date = date(selected_year, selected_month, 1)
        selected_location = self.request.POST.get('selectedLocation')
        selected_ministry = self.request.POST.get('selectedMinistry')
        beneficiary_type = self.request.POST.get('selectedBeneficiaryType')
        draw = self.request.POST.get('draw', 0)
        length = int(self.request.POST.get('length', 0))
        start = int(self.request.POST.get('start', 0))
        sort_column = self.request.POST.get('sortColumn', 'name')
        sort_column_dir = self.request.POST.get('sortColumnDir', 'asc')

        location_filters = build_location_filters(selected_location, selected_ministry, with_child=False)

        if sort_column_dir == 'desc':
            sort_column = '-' + sort_column
        data = []
        if beneficiary_type == 'child':
            data = (
                Child.objects.annotate(
                    age=ExtractYear(Func(F('dob'), function='age')),
                ).filter(
                    domain=request.domain,
                    age__range=(0, 5),
                    **location_filters
                ).extra(
                    select={
                        'lastImmunizationType': '\'N/A\'',
                        'lastImmunizationDate': '\'N/A\'',
                        'gender': 'sex',
                        'id': 'person_case_id'
                    }
                ).values(
                    'id', 'name', 'age', 'gender',
                    'lastImmunizationType', 'lastImmunizationDate'
                ).order_by(sort_column)
            )
        elif beneficiary_type == 'eligible_couple':
            data = (
                Woman.objects.annotate(
                    age=ExtractYear(Func(F('dob'), function='age')),
                ).filter(
                    domain=request.domain,
                    age__range=(15, 49),
                    marital_status='married',
                    **location_filters
                ).exclude(migration_status='yes').extra(
                    select={
                        'currentFamilyPlanningMethod': '\'N/A\'',
                        'adoptionDateOfFamilyPlaning': '\'N/A\'',
                        'id': 'person_case_id',
                    },
                    where=["NOT daterange(%s, %s) && any(pregnant_ranges)"],
                    params=[selected_date, selected_date + relativedelta(months=1)]
                ).values(
                    'id', 'name', 'age',
                    'currentFamilyPlanningMethod', 'adoptionDateOfFamilyPlaning'
                ).order_by(sort_column)
            )
        elif beneficiary_type == 'pregnant_women':
            data = (
                Woman.objects.annotate(
                    age=ExtractYear(Func(F('dob'), function='age')),
                ).filter(
                    domain=request.domain,
                    **location_filters
                ).extra(
                    select={
                        'highRiskPregnancy': '\'N/A\'',
                        'noOfAncCheckUps': '\'N/A\'',
                        'pregMonth': '\'N/A\'',
                        'id': 'person_case_id',
                    },
                    where=["daterange(%s, %s) && any(pregnant_ranges)"],
                    params=[selected_date, selected_date + relativedelta(months=1)]
                ).values(
                    'id', 'name', 'age', 'pregMonth',
                    'highRiskPregnancy', 'noOfAncCheckUps'
                ).order_by(sort_column)
            )
        if data:
            number_of_data = data.count()
            data = data[start:start + length]
        else:
            number_of_data = 0
        data = list(data)
        return JsonResponse(data={
            'rows': data,
            'draw': draw,
            'recordsTotal': number_of_data,
            'recordsFiltered': number_of_data,
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
        if settings.SERVER_ENVIRONMENT != 'india':
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

        if sub_section == 'person_details':
            person_model = Woman if section != 'child' else Child

            values = [
                'dob', 'name', 'sex', 'has_aadhar_number', 'hh_address', 'contact_phone_number',
                'hh_religion', 'hh_caste', 'hh_bpl_apl', 'sc_id', 'village_id', 'awc_id'
            ]

            if section != 'child':
                values.extend([
                    'migration_status',
                    'age_marriage',
                    'husband_name'
                ])
            else:
                values.append('mother_case_id')

            person = person_model.objects.values(*values).get(
                domain=request.domain,
                person_case_id=beneficiary_id
            )

            location_details = SQLLocation.objects.filter(
                domain=request.domain,
                location_id__in=[person['sc_id'], person['village_id'], person['awc_id']]
            )

            for location in location_details:
                person[location.location_type.code] = location.name

            data = dict(
                person=person,
            )

            if section == 'child':
                mother = Woman.objects.extra(
                    select={
                        'id': 'person_case_id'
                    }
                ).values('id', 'name').get(person_case_id=person['mother_case_id'])
                data.update(dict(mother=mother))
            else:
                # TODO update when the model will be created
                husband = dict(
                    name=person['husband_name'],
                    sex='Female',
                    dob=date(1991, 5, 11),
                    age_marriage=26,
                    has_aadhar_number='Yes'
                )
                data.update(dict(husband=husband))
        elif sub_section == 'child_details':
            data = dict(
                children=list(Child.objects.filter(
                    domain=request.domain,
                    mother_case_id=beneficiary_id
                ).extra(
                    select={
                        'id': 'person_case_id'
                    }
                ).values('id', 'name', 'dob'))
            )

        if section == 'child':
            helper = ChildQueryHelper(request.domain, beneficiary_id)
            if sub_section == 'infant_details':
                data = helper.infant_details()
            elif sub_section == 'child_postnatal_care_details':
                data = {'visits': helper.postnatal_care_details()}
            elif sub_section == 'vaccination_details':
                period = self.request.POST.get('period', 'atBirth')
                data = {'vitamins': helper.vaccination_details(period)}
            elif sub_section == 'growth_monitoring':
                data = helper.growth_monitoring()
            elif sub_section == 'weight_for_age_chart':
                data = {'points': helper.weight_for_age_chart()}
            elif sub_section == 'height_for_age_chart':
                data = {'points': helper.height_for_age_chart()}
            elif sub_section == 'weight_for_height_chart':
                data = {'points': helper.weight_for_height_chart()}
        elif section == 'pregnant_women':
            helper = PregnantWomanQueryHelper(request.domain, beneficiary_id)
            if sub_section == 'pregnancy_details':
                data = helper.pregnancy_details()
            elif sub_section == 'pregnancy_risk':
                data = helper.pregnancy_risk()
            elif sub_section == 'consumables_disbursed':
                data = helper.consumables_disbursed()
            elif sub_section == 'immunization_counseling_details':
                data = helper.immunization_counseling_details()
            elif sub_section == 'abortion_details':
                data = helper.abortion_details()
            elif sub_section == 'maternal_death_details':
                data = helper.maternal_death_details()
            elif sub_section == 'delivery_details':
                data = helper.delivery_details()
            elif sub_section == 'postnatal_care_details':
                data = {'visits': helper.postnatal_care_details()}
            elif sub_section == 'antenatal_care_details':
                data = {'visits': helper.antenatal_care_details()}
        elif section == 'eligible_couple':
            if sub_section == 'eligible_couple_details':
                data = EligibleCoupleQueryHelper(request.domain, beneficiary_id).eligible_couples_details()

        if not data:
            raise Http404()
        return JsonResponse(data=data)
