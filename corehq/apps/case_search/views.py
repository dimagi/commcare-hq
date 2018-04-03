from __future__ import absolute_import
from __future__ import unicode_literals
import json
import re

from corehq.apps.domain.decorators import cls_require_superuser_or_developer
from corehq.apps.domain.views import DomainViewMixin
from django.http import Http404
from dimagi.utils.web import json_response
from django.views.generic import TemplateView
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_MAX_RESULTS
from corehq.apps.case_search.models import case_search_enabled_for_domain, CaseSearchQueryAddition, merge_queries
from corehq.util.view_utils import json_error, BadRequest


class CaseSearchView(DomainViewMixin, TemplateView):
    template_name = 'case_search/case_search.html'
    urlname = 'case_search'

    @cls_require_superuser_or_developer
    def get(self, request, *args, **kwargs):
        if not case_search_enabled_for_domain(self.domain):
            raise Http404("Domain does not have case search enabled")

        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super(CaseSearchView, self).get_context_data(**kwargs)
        query_additions = CaseSearchQueryAddition.objects.filter(domain=self.domain)
        context.update({
            "query_additions": query_additions,
        })
        return context

    @json_error
    @cls_require_superuser_or_developer
    def post(self, request, *args, **kwargs):
        from corehq.apps.es.case_search import CaseSearchES
        if not case_search_enabled_for_domain(self.domain):
            raise BadRequest("Domain does not have case search enabled")

        query = json.loads(request.POST.get('q'))
        case_type = query.get('type')
        owner_id = query.get('owner_id')
        search_params = query.get('parameters', [])
        query_addition = query.get("customQueryAddition", None)
        include_closed = query.get("includeClosed", False)
        search = CaseSearchES()
        search = search.domain(self.domain).size(CASE_SEARCH_MAX_RESULTS)
        if not include_closed:
            search = search.is_closed(False)
        if case_type:
            search = search.case_type(case_type)
        if owner_id:
            search = search.owner(owner_id)
        for param in search_params:
            value = re.sub(param.get('regex', ''), '', param.get('value'))
            search = search.case_property_query(
                param.get('key'),
                value,
                clause=param.get('clause'),
                fuzzy=param.get('fuzzy'),
            )
        if query_addition:
            addition = CaseSearchQueryAddition.objects.get(id=query_addition, domain=self.domain)
            new_query = merge_queries(search.get_query(), addition.query_addition)
            search = search.set_query(new_query)
        search_results = search.run()
        return json_response({'values': search_results.raw_hits, 'count': search_results.total})
