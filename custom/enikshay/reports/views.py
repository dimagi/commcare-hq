from collections import defaultdict, Counter

from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.views.generic.base import View

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.locations.permissions import location_safe
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceQueryContext, LocationChoiceProvider
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import CASE_TYPE_VOUCHER, CASE_TYPE_PERSON
from custom.enikshay.const import VOUCHER_ID, ENIKSHAY_ID
from custom.enikshay.reports.utils import StubReport


@location_safe
class LocationsView(View):

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
        location_choice_provider = LocationChoiceProvider(StubReport(domain=domain), None)
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


@domain_admin_required
def duplicate_ids_report(request, domain, case_type):
    case_type = {'voucher': CASE_TYPE_VOUCHER, 'person': CASE_TYPE_PERSON}[case_type]
    id_property = {'voucher': VOUCHER_ID, 'person': ENIKSHAY_ID}[case_type]

    accessor = CaseAccessors(domain)
    case_ids = accessor.get_case_ids_in_domain(case_type)
    all_cases = list(accessor.iter_cases(case_ids))
    counts = Counter(case.get_case_property(id_property) for case in all_cases)
    bad_cases = sorted([
        {
            'case_id': case.case_id,
            'readable_id': case.get_case_property(id_property),
            'opened_on': case.opened_on,
        }
        for case in all_cases
        if counts[case.get_case_property(id_property)] > 1
    ], key=lambda case: case['opened_on'], reverse=True)

    context = {
        'case_type': case_type,
        'num_bad_cases': len(bad_cases),
        'num_total_cases': len(all_cases),
        'num_good_cases': len(all_cases) - len(bad_cases),
        'bad_cases': bad_cases,
    }
    return render(request, 'enikshay/duplicate_ids_report.html', context)
