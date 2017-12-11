from __future__ import absolute_import

from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.views.generic.base import View, TemplateView

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.es import CaseES
from corehq.apps.locations.permissions import location_safe
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceQueryContext, LocationChoiceProvider
from custom.enikshay.case_utils import CASE_TYPE_VOUCHER, CASE_TYPE_PERSON
from custom.enikshay.duplicate_ids import get_cases_with_duplicate_ids, add_debug_info_to_cases
from custom.enikshay.reports.utils import StubReport
from custom.enikshay.reports.choice_providers import DistrictChoiceProvider


@location_safe
class LocationsView(View):
    choice_provider = LocationChoiceProvider

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LocationsView, self).dispatch(*args, **kwargs)

    def get(self, request, domain, *args, **kwargs):
        user = self.request.couch_user

        query_context = ChoiceQueryContext(
            query=request.GET.get('q', None),
            limit=int(request.GET.get('limit', 20)),
            page=int(request.GET.get('page', 1)) - 1,
            user=user
        )
        location_choice_provider = self.choice_provider(StubReport(domain=domain), None)
        location_choice_provider.configure({
            'include_descendants': True,
            'order_by_hierarchy': True,
            'show_full_path': True,
        })
        return JsonResponse(
            {
                'results': [
                    {'id': location.value, 'text': location.display}
                    for location in location_choice_provider.query(query_context)
                ],
                'total': location_choice_provider.query_count(query_context.query, user)
            }
        )


@location_safe
class DistrictLocationsView(LocationsView):
    choice_provider = DistrictChoiceProvider


@method_decorator(domain_admin_required, name='dispatch')
class DuplicateIdsReport(TemplateView):
    def get(self, request, domain, case_type, *args, **kwargs):
        case_type = {'voucher': CASE_TYPE_VOUCHER, 'person': CASE_TYPE_PERSON}[case_type]
        # By default, only show full debug info for the 300 most recent cases
        limit_debug_to = None if request.GET.get('full_debug_info') else 300
        context = self.get_duplicate_id_case_info(domain, case_type, limit_debug_to)
        return render(request, 'enikshay/duplicate_ids_report.html', context)

    @staticmethod
    def get_duplicate_id_case_info(domain, case_type, limit_debug_to=None):
        total_cases = CaseES().domain(domain).case_type(case_type).count()
        bad_cases = get_cases_with_duplicate_ids(domain, case_type)
        add_debug_info_to_cases(bad_cases, limit_debug_to)
        context = {
            'case_type': case_type,
            'num_bad_cases': len(bad_cases),
            'num_total_cases': total_cases,
            'num_good_cases': total_cases - len(bad_cases),
            'bad_cases': bad_cases,
        }
        return context
