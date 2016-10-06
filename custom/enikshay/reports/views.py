from collections import namedtuple

from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceQueryContext, LocationChoiceProvider


Report = namedtuple('Report', 'domain')


class LocationsView(View):

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LocationsView, self).dispatch(*args, **kwargs)

    def get(self, request, domain, *args, **kwargs):
        query_context = ChoiceQueryContext(
            query=request.GET.get('q', None),
            limit=int(request.GET.get('limit', 20)),
            page=int(request.GET.get('page', 1)) - 1
        )
        location_choice_provider = LocationChoiceProvider(Report(domain=domain), None)
        location_choice_provider.configure({'include_descendants': True})
        return JsonResponse(
            {
                'results': [
                    {'id': location.value, 'text': location.display}
                    for location in location_choice_provider.query(query_context)
                ],
                'total': location_choice_provider.query_count(query_context)
            }
        )
