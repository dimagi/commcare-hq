import json

from corehq.apps.domain.decorators import cls_require_developer
from corehq.apps.domain.views import DomainViewMixin
from django.http import Http404
from dimagi.utils.web import json_response
from django.views.generic import TemplateView
from corehq.apps.case_search.models import case_search_enabled_for_domain
from corehq.util.view_utils import json_error, BadRequest


class CaseSearchView(DomainViewMixin, TemplateView):
    template_name = 'case_search/case_search.html'
    urlname = 'case_search'

    @cls_require_developer
    def get(self, request, *args, **kwargs):
        if not case_search_enabled_for_domain(self.domain):
            raise Http404("Domain does not have case search enabled")

        return self.render_to_response(self.get_context_data())

    @json_error
    @cls_require_developer
    def post(self, request, *args, **kwargs):
        from corehq.apps.es.case_search import CaseSearchES
        if not case_search_enabled_for_domain(self.domain):
            raise BadRequest("Domain does not have case search enabled")

        query = json.loads(request.POST.get('q'))
        case_type = query.get('type')
        search_params = query.get('parameters', [])
        search = CaseSearchES()
        search = search.domain(self.domain).is_closed(False)
        if case_type:
            search = search.case_type(case_type)
        for param in search_params:
            search = search.case_property_query(**param)
        search_results = search.values()
        return json_response({'values': search_results})
