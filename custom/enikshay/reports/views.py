from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.permissions import location_safe
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceQueryContext, LocationChoiceProvider
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
