import json

from corehq.apps.domain.views import DomainViewMixin
from dimagi.utils.web import json_response
from django.views.generic import TemplateView


# Create your views here.
class CaseSearchView(DomainViewMixin, TemplateView):
    template_name = 'case_search/case_search.html'
    urlname = 'case_search'

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        from corehq.apps.es.case_search import CaseSearchES
        query = json.loads(request.POST.get('q'))
        case_type = query.get('type')
        search_params = query.get('parameters')
        search = CaseSearchES()
        search = search.domain(self.domain)
        if case_type:
            search = search.case_type(case_type)
        for param in search_params:
            search = search.case_property_query(**param)
        search_results = search.values()
        return json_response({'values': search_results})
