from __future__ import absolute_import
from __future__ import unicode_literals

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView, View

from custom.reach.const import INDICATOR_LIST, NUMERIC, PERCENT, COLORS


class ReachDashboardView(TemplateView):
    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def couch_user(self):
        return self.request.couch_user

    def get_context_data(self, **kwargs):
        kwargs['domain'] = self.domain
        # TODO add logic for user role type possible options should be MoHFW or MWCD
        kwargs['user_role_type'] = 'MoHFW'
        user_location = self.couch_user.get_sql_locations(self.domain).first()
        kwargs['user_location_id'] = user_location.location_id if user_location else None

        user_locations_with_parents = SQLLocation.objects.get_queryset_ancestors(
            user_location, include_self=True
        ).distinct() if user_location else []
        parent_ids = [loc.location_id for loc in user_locations_with_parents]
        kwargs['user_location_ids'] = parent_ids
        return super(ReachDashboardView, self).get_context_data(**kwargs)


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class ProgramOverviewReport(ReachDashboardView):
    template_name = 'reach/reports/program_overview.html'


@location_safe
@method_decorator([login_and_domain_required, csrf_exempt], name='dispatch')
class ProgramOverviewReportAPI(View):
    def post(self, request, *args, **kwargs):
        # TODO add query to database
        selected_month = int(self.request.POST.get('selectedMonth'))
        selected_year = int(self.request.POST.get('selectedYear'))
        selected_location = self.request.POST.get('selectedLocation')
        return JsonResponse(data={'data': [
            [
                {
                    'indicator': INDICATOR_LIST['registered_eligible_couples'],
                    'format': NUMERIC,
                    'color': COLORS['violet'],
                    'numerator': 71682,
                    'denominator': 140098,
                    'past_month_numerator': 69354,
                    'past_month_denominator': 130098
                },
                {
                    'indicator': INDICATOR_LIST['registered_pregnancies'],
                    'format': NUMERIC,
                    'color': COLORS['blue'],
                    'numerator': 9908,
                    'denominator': 128990,
                    'past_month_numerator': 12458,
                    'past_month_denominator': 115800
                },
                {
                    'indicator': INDICATOR_LIST['registered_children'],
                    'format': NUMERIC,
                    'color': COLORS['orange'],
                    'numerator': 21630,
                    'denominator': 890743,
                    'past_month_numerator': 40687,
                    'past_month_denominator': 715486
                }
            ],
            [
                {
                    'indicator': INDICATOR_LIST['couples_family_planning'],
                    'format': PERCENT,
                    'color': COLORS['aqua'],
                    'numerator': 65028,
                    'denominator': 928103,
                    'past_month_numerator': 60486,
                    'past_month_denominator': 914384
                },
                {
                    'indicator': INDICATOR_LIST['high_risk_pregnancies'],
                    'format': PERCENT,
                    'color': COLORS['darkorange'],
                    'numerator': 207,
                    'denominator': 9908,
                    'past_month_numerator': 204,
                    'past_month_denominator': 9837
                },
                {
                    'indicator': INDICATOR_LIST['institutional_deliveries'],
                    'format': PERCENT,
                    'color': COLORS['mediumblue'],
                    'numerator': 14311,
                    'denominator': 21837,
                    'past_month_numerator': 16486,
                    'past_month_denominator': 21648
                }
            ]
        ]})


@location_safe
@method_decorator([login_and_domain_required], name='dispatch')
class UnifiedBeneficiaryReport(ReachDashboardView):
    template_name = 'reach/reports/unified_beneficiary.html'


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
