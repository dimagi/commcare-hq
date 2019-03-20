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

            extra_select = {
                'gender': 'sex',
                'aadhaarNo': 'has_aadhar_number',
                'address': 'hh_address',
                'phone': 'contact_phone_number',
                'religion': 'hh_religion',
                'caste': 'hh_caste',
                'bplOrApl': 'hh_bpl_apl',
                'subcentre': 'sc_id',
                'village': 'village_id',
                'anganwadiCentre': 'awc_id'
            }

            if section != 'child':
                extra_select.update({
                    'status': 'migration_status',
                    'marriedAt': 'age_marriage',
                    'husband_name': 'husband_name'
                })
            else:
                extra_select.update({
                    'mother_case_id': 'mother_case_id'
                })

            extra_select_values = list(extra_select.keys())
            extra_select_values.extend(
                ['dob', 'name']
            )
            person = person_model.objects.extra(
                select=extra_select
            ).values(*extra_select_values).get(
                domain=request.domain,
                person_case_id=beneficiary_id
            )

            subsentre = SQLLocation.objects.get(domain=request.domain, location_id=person['subcentre']).name
            village = SQLLocation.objects.get(domain=request.domain, location_id=person['village']).name
            anganwadiCentre = SQLLocation.objects.get(domain=request.domain, location_id=person['anganwadiCentre']).name
            person['subcentre'] = subsentre
            person['village'] = village
            person['anganwadiCentre'] = anganwadiCentre

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
                    gender='Female',
                    dob=date(1991, 5, 11),
                    marriedAt=26,
                    aadhaarNo='Yes'
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
            if sub_section == 'infant_details':
                extra_select = {
                    'breastfeedingInitiated': 'breastfed_within_first',
                    'dietDiversity': 'diet_diversity',
                    'birthWeight': 'birth_weight',
                    'dietQuantity': 'diet_quantity',
                    'breastFeeding': 'comp_feeding',
                    'handwash': 'hand_wash',
                    'exclusivelyBreastfed': 'is_exclusive_breastfeeding',
                    'babyCried': '\'N/A\'',
                    'pregnancyLength': '\'N/A\'',
                }

                data = Child.objects.extra(
                    select=extra_select
                ).values(*list(extra_select.keys())).get(
                    domain=request.domain,
                    person_case_id=beneficiary_id,
                )
            elif sub_section == 'child_postnatal_care_details':
                # TODO update when CcsRecord will have properties from PNC form
                data = dict(
                    visits=[
                        dict(
                            pncDate='N/A',
                            breastfeeding='N/A',
                            skinToSkinContact='N/A',
                            wrappedUpAdequately='N/A',
                            awakeActive='N/A',
                        )
                    ]
                )
            elif sub_section == 'vaccination_details':
                period = self.request.POST.get('period', 'atBirth')
                if period == 'atBirth':
                    data = dict(
                        vitamins=[
                            dict(
                                vitaminName='BCG',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Hepatitis B - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='OPV - 0',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                        ]
                    )
                elif period == 'sixWeek':
                    data = dict(
                        vitamins=[
                            dict(
                                vitaminName='OPV - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Pentavalent - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Fractional IPV - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Rotavirus - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='PCV - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                        ]
                    )
                elif period == 'tenWeek':
                    data = dict(
                        vitamins=[
                            dict(
                                vitaminName='OPV - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Pentavalent - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Rotavirus - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                        ]
                    )
                elif period == 'fourteenWeek':
                    data = dict(
                        vitamins=[
                            dict(
                                vitaminName='OPV - 3',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Pentavalent - 3',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Fractional IPV - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Rotavirus - 3',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='PCV - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                        ]
                    )
                elif period == 'nineTwelveMonths':
                    data = dict(
                        vitamins=[
                            dict(
                                vitaminName='PCV Booster',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Measles - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='JE - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                        ]
                    )
                elif period == 'sixTeenTwentyFourMonth':
                    data = dict(
                        vitamins=[
                            dict(
                                vitaminName='DPT Booster - 1',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Measles - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='OPV Booster',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='JE - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 3',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                        ]
                    )
                elif period == 'twentyTwoSeventyTwoMonth':
                    data = dict(
                        vitamins=[
                            dict(
                                vitaminName='Vit. A - 4',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 5',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 6',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 7',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 8',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='Vit. A - 9',
                                date='N/A',
                                adverseEffects='N/A',
                            ),
                            dict(
                                vitaminName='DPT Booster - 2',
                                date='N/A',
                                adverseEffects='N/A',
                            )
                        ]
                    )
            elif sub_section == 'growth_monitoring':
                data = dict(
                    currentWeight='N/A',
                    nrcReferred='N/A',
                    growthMonitoringStatus='N/A',
                    referralDate='N/A',
                    previousGrowthMonitoringStatus='N/A',
                    underweight='N/A',
                    underweightStatus='N/A',
                    stunted='N/A',
                    stuntedStatus='N/A',
                    wasting='N/A',
                    wastingStatus='N/A',
                )
            elif sub_section == 'weight_for_age_chart':
                child = Child.objects.get(person_case_id=beneficiary_id)
                try:
                    child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
                    points = []
                    for recorded_weight in child_history.weight_child_history:
                        month = relativedelta(recorded_weight[0], child.dob).months
                        points.append(dict(x=month, y=recorded_weight[1]))
                except ChildHistory.DoesNotExist:
                    points = []
                data = dict(
                    points=points
                )
            elif sub_section == 'height_for_age_chart':
                child = Child.objects.get(person_case_id=beneficiary_id)
                try:
                    child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
                    points = []
                    for recorded_height in child_history.height_child_history:
                        month = relativedelta(recorded_height[0], child.dob).months
                        points.append(dict(x=month, y=recorded_height[1]))
                except ChildHistory.DoesNotExist:
                    points = []
                data = dict(
                    points=points
                )
            elif sub_section == 'weight_for_height_chart':
                child = Child.objects.get(person_case_id=beneficiary_id)
                try:
                    child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
                    points = {}
                    for recorded_weight in child_history.weight_child_history:
                        month = relativedelta(recorded_weight[0], child.dob).months
                        points.update({month: dict(x=recorded_weight[1])})
                    for recorded_height in child_history.height_child_history:
                        month = relativedelta(recorded_height[0], child.dob).months
                        if month in points:
                            points[month].update(dict(y=recorded_height[1]))
                        else:
                            points.update({month: dict(y=recorded_height[1])})
                except ChildHistory.DoesNotExist:
                    points = {}
                data = dict(
                    points=[point for point in points.values() if 'x' in point and 'y']
                )
        elif section == 'pregnant_women':
            if sub_section == 'pregnancy_details':
                data = CcsRecord.objects.extra(
                    select={
                        'dateOfLmp': 'lmp',
                        'weightOfPw': 'woman_weight_at_preg_reg',
                        'dateOfRegistration': 'preg_reg_date',
                    }
                ).values(
                    'lmp', 'weightOfPw', 'dateOfRegistration', 'edd', 'add'
                ).get(person_case_id=beneficiary_id)
                # I think we should consider to add blood_group to the CcsRecord to don't have two queries
                data.update(
                    Woman.objects.extra(
                        select={
                            'bloodGroup': 'blood_group'
                        }
                    ).values('bloodGroup').get(
                        person_case_id=beneficiary_id
                    )
                )
            elif sub_section == 'pregnancy_risk':
                data = dict(
                    riskPregnancy='N/A',
                    referralDate='N/A',
                    hrpSymptoms='N/A',
                    illnessHistory='N/A',
                    referredOutFacilityType='N/A',
                    pastIllnessDetails='N/A',
                )
            elif sub_section == 'consumables_disbursed':
                data = dict(
                    ifaTablets='N/A',
                    thrDisbursed='N/A',
                )
            elif sub_section == 'immunization_counseling_details':
                data = dict(
                    ttDoseOne='N/A',
                    ttDoseTwo='N/A',
                    ttBooster='N/A',
                    birthPreparednessVisitsByAsha='N/A',
                    birthPreparednessVisitsByAww='N/A',
                    counsellingOnMaternal='N/A',
                    counsellingOnEbf='N/A',
                )
            elif sub_section == 'abortion_details':
                data = dict(
                    abortionDate='N/A',
                    abortionType='N/A',
                    abortionDays='N/A',
                )
            elif sub_section == 'maternal_death_details':
                data = dict(
                    maternalDeathOccurred='N/A',
                    maternalDeathPlace='N/A',
                    maternalDeathDate='N/A',
                    authoritiesInformed='N/A',
                )
            elif sub_section == 'delivery_details':
                data = dict(
                    dod='N/A',
                    assistanceOfDelivery='N/A',
                    timeOfDelivery='N/A',
                    dateOfDischarge='N/A',
                    typeOfDelivery='N/A',
                    timeOfDischarge='N/A',
                    placeOfBirth='N/A',
                    deliveryComplications='N/A',
                    placeOfDelivery='N/A',
                    complicationDetails='N/A',
                    hospitalType='N/A',
                )
            elif sub_section == 'postnatal_care_details':
                data = dict(
                    visits=[
                        dict(
                            pncDate='2019-08-20',
                            postpartumHeamorrhage=0,
                            fever=1,
                            convulsions=0,
                            abdominalPain=0,
                            painfulUrination=0,
                            congestedBreasts=1,
                            painfulNipples=0,
                            otherBreastsIssues=0,
                            managingBreastProblems=0,
                            increasingFoodIntake=1,
                            possibleMaternalComplications=1,
                            beneficiaryStartedEating=0,
                        )
                    ]
                )
            elif sub_section == 'antenatal_care_details':
                data = dict(
                    visits=[
                        dict(
                            ancDate='N/A',
                            ancLocation='N/A',
                            pwWeight='N/A',
                            bloodPressure='N/A',
                            hb='N/A',
                            abdominalExamination='N/A',
                            abnormalitiesDetected='N/A',
                        ),
                    ]
                )
        elif section == 'eligible_couple':
            if sub_section == 'eligible_couple_details':
                data = dict(
                    maleChildrenBorn='N/A',
                    femaleChildrenBorn='N/A',
                    maleChildrenAlive='N/A',
                    femaleChildrenAlive='N/A',
                    familyPlaningMethod='N/A',
                    familyPlanningMethodDate='N/A',
                    ashaVisit='N/A',
                    previousFamilyPlanningMethod='N/A',
                    preferredFamilyPlaningMethod='N/A'
                )

        if not data:
            raise Http404()
        return JsonResponse(data=data)
