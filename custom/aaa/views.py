from __future__ import absolute_import, unicode_literals

from datetime import date

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.http.response import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView, View

from celery.result import AsyncResult
from dateutil.relativedelta import relativedelta

from couchexport.models import Format
from dimagi.utils.dates import force_to_date

from corehq.apps.domain.decorators import (
    login_and_domain_required,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.hqwebapp.views import no_permissions
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from corehq.util.files import safe_filename_header
from custom.aaa.const import COLORS, INDICATOR_LIST, NUMERIC, PERCENT
from custom.aaa.dbaccessors import (
    ChildQueryHelper,
    EligibleCoupleQueryHelper,
    PregnantWomanQueryHelper,
)
from custom.aaa.models import Child, Woman
from custom.aaa.tasks import prepare_export_reports, run_aggregation
from custom.aaa.utils import (
    build_location_filters,
    get_file_from_blobdb,
    get_location_model_for_ministry,
)


@location_safe
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

        selected_location = self.request.GET.get('selectedLocation', '')
        if selected_location:
            location = SQLLocation.objects.get(location_id=selected_location)
            selected_hierarchy = [loc.location_id for loc in location.get_ancestors(include_self=True)]
            kwargs['selected_location_ids'] = selected_hierarchy
        return super(ReachDashboardView, self).get_context_data(**kwargs)


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
        next_month_start = selected_date + relativedelta(months=1)
        selected_location = self.request.POST.get('selectedLocation')
        selected_ministry = self.request.POST.get('selectedMinistry')
        beneficiary_type = self.request.POST.get('selectedBeneficiaryType')
        draw = self.request.POST.get('draw', 0)
        length = int(self.request.POST.get('length', 0))
        start = int(self.request.POST.get('start', 0))
        sort_column = self.request.POST.get('sortColumn', 'name')
        sort_column_dir = self.request.POST.get('sortColumnDir', 'asc')

        location_filters = build_location_filters(selected_location, selected_ministry, with_child=False)
        sort_column_with_dir = sort_column
        if sort_column_dir == 'desc':
            sort_column_with_dir = '-' + sort_column
        data = []
        if beneficiary_type == 'child':
            data = ChildQueryHelper.list(request.domain, next_month_start, location_filters, sort_column_with_dir)
        elif beneficiary_type == 'eligible_couple':
            sort_column_with_dir = '"%s" %s' % (sort_column, sort_column_dir)
            data = EligibleCoupleQueryHelper.list(
                request.domain,
                selected_date,
                location_filters,
                sort_column_with_dir
            )
        elif beneficiary_type == 'pregnant_women':
            sort_column_with_dir = '"%s" %s' % (sort_column, sort_column_dir)
            data = PregnantWomanQueryHelper.list(
                request.domain,
                selected_date,
                location_filters,
                sort_column_with_dir
            )
        if data:
            number_of_data = len(data)
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
        selected_location = self.request.POST.get('parentSelectedId', None)
        location_type = self.request.POST.get('locationType', None)
        domain = self.kwargs['domain']
        locations = SQLLocation.objects.filter(
            domain=domain,
            location_type__code=location_type
        ).order_by('name')

        if selected_location:
            locations = locations.filter(parent__location_id=selected_location).order_by('name')

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
    urlname = 'aaa_aggregation_script_page'
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
        run_aggregation(self.domain, date)
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

        person_model = Woman if context['selected_type'] != 'child' else Child

        village_id = person_model.objects.get(person_case_id=context['beneficiary_id']).village_id

        locations = SQLLocation.objects.get(
            domain=request.domain, location_id=village_id
        ).get_ancestors(include_self=True)

        context['beneficiary_location_names'] = [
            loc.name for loc in locations
        ]
        return self.render_to_response(context)


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class UnifiedBeneficiaryDetailsReportAPI(View):
    def post(self, request, *args, **kwargs):
        selected_month = int(self.request.POST.get('selectedMonth', 0))
        selected_year = int(self.request.POST.get('selectedYear', 0))
        month_end = date(selected_year, selected_month, 1) + relativedelta(months=1) - relativedelta(days=1)
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
                    'husband_name',
                    'marital_status'
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
                    sex='N/A',
                    dob='N/A',
                    age_marriage='N/A',
                    has_aadhar_number='N/A'
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
            helper = ChildQueryHelper(request.domain, beneficiary_id, month_end)
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
            helper = PregnantWomanQueryHelper(request.domain, beneficiary_id, month_end)
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
            helper = EligibleCoupleQueryHelper(request.domain, beneficiary_id, month_end)
            if sub_section == 'eligible_couple_details':
                data = helper.eligible_couple_details()

        if not data:
            raise Http404()
        return JsonResponse(data=data)


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class ExportData(View):
    def post(self, request, *args, **kwargs):
        selected_month = int(self.request.POST.get('selectedMonth'))
        selected_year = int(self.request.POST.get('selectedYear'))
        selected_date = date(selected_year, selected_month, 1)
        next_month_start = selected_date + relativedelta(months=1)
        selected_location = self.request.POST.get('selectedLocation')
        selected_ministry = self.request.POST.get('selectedMinistry')
        beneficiary_type = self.request.POST.get('selectedBeneficiaryType')

        task = prepare_export_reports.delay(
            request.domain,
            selected_date,
            next_month_start,
            selected_location,
            selected_ministry,
            beneficiary_type
        )
        return JsonResponse(data={
            'task_id': task.task_id
        })


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class CheckExportTask(View):
    def get(self, request, *args, **kwargs):
        task_id = self.kwargs.get('task_id', None)
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
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class DownloadFile(View):
    def get(self, request, *args, **kwargs):
        file_id = self.kwargs.get('file_id', None)
        content_type = Format.from_format('xlsx')
        response = HttpResponse(
            get_file_from_blobdb(file_id).read(),
            content_type=content_type.mimetype
        )
        response['Content-Disposition'] = safe_filename_header(
            'unified_beneficiary_list',
            content_type.extension
        )
        return response
