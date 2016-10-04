from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.reports.filters.choice_providers import ChoiceQueryContext


class LocationsView(View):

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LocationsView, self).dispatch(*args, **kwargs)

    def _locations_query(self, domain, query_text):
        if query_text:
            return SQLLocation.active_objects.filter_path_by_user_input(
                domain=domain, user_input=query_text)
        else:
            return SQLLocation.active_objects.filter(domain=domain)

    def query(self, domain, query_context):
        locations = self._locations_query(domain, query_context.query).order_by('name')

        return [
            {'id': loc.location_id, 'text': loc.display_name}
            for loc in locations[query_context.offset:query_context.offset + query_context.limit]
        ]

    def query_count(self, domain, query):
        return self._locations_query(domain, query).count()

    def get(self, request, domain, *args, **kwargs):
        query_context = ChoiceQueryContext(
            query=request.GET.get('q', None),
            limit=int(request.GET.get('limit', 20)),
            page=int(request.GET.get('page', 1)) - 1
        )
        return JsonResponse(
            {
                'results': self.query(domain, query_context),
                'total': self.query_count(domain, query_context)
            }
        )
