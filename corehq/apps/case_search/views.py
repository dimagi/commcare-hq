import json
import re
from datetime import datetime

from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext_lazy

from dimagi.utils.web import json_response

from corehq.apps.case_search.models import (
    case_search_enabled_for_domain,
    extract_search_request_config,
)
from corehq.apps.case_search.utils import profile_case_search
from corehq.apps.domain.decorators import cls_require_superuser_or_contractor
from corehq.apps.domain.views.base import BaseDomainView
from corehq.util.view_utils import BadRequest, json_error


class _BaseCaseSearchView(BaseDomainView):
    section_name = gettext_lazy("Data")

    @property
    def section_url(self):
        return reverse("data_interfaces_default", args=[self.domain])

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @cls_require_superuser_or_contractor
    def get(self, request, *args, **kwargs):
        if not case_search_enabled_for_domain(self.domain):
            raise Http404("Domain does not have case search enabled")

        return self.render_to_response(self.get_context_data())


class CaseSearchView(_BaseCaseSearchView):
    template_name = 'case_search/bootstrap3/case_search.html'
    urlname = 'case_search'
    page_title = gettext_lazy("Case Search")

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'settings_url': reverse("case_search_config", args=[self.domain]),
        })
        return context

    @json_error
    @cls_require_superuser_or_contractor
    def post(self, request, *args, **kwargs):
        from corehq.apps.es.case_search import CaseSearchES
        if not case_search_enabled_for_domain(self.domain):
            raise BadRequest("Domain does not have case search enabled")

        query = json.loads(request.POST.get('q'))
        case_type = query.get('type')
        owner_id = query.get('owner_id')
        search_params = query.get('parameters', [])
        xpath_expressions = query.get("xpath_expressions", [])
        search = CaseSearchES()
        search = search.domain(self.domain).size(10)
        if case_type:
            search = search.case_type(case_type)
        if owner_id:
            search = search.owner(owner_id)
        for param in search_params:
            value = re.sub(param.get('regex', ''), '', param.get('value'))
            if '/' in param.get('key'):
                query = '{} = "{}"'.format(param.get('key'), value)
                search = search.xpath_query(self.domain, query, fuzzy=param.get('fuzzy'))
            else:
                search = search.case_property_query(
                    param.get('key'),
                    value,
                    clause=param.get('clause'),
                    fuzzy=param.get('fuzzy'),
                )

        for xpath in filter(None, xpath_expressions):
            search = search.xpath_query(self.domain, xpath)

        include_profile = request.POST.get("include_profile", False)
        if include_profile:
            search = search.enable_profiling()

        search_results = search.run()
        return json_response({
            'values': search_results.raw_hits,
            'count': search_results.total,
            'took': search_results.raw['took'],
            'query': search_results.query.dumps(pretty=True),
            'profile': json.dumps(search_results.raw.get('profile', {}), indent=2),
        })


class ProfileCaseSearchView(_BaseCaseSearchView):
    template_name = 'case_search/profile_case_search.html'
    urlname = 'profile_case_search'
    page_title = gettext_lazy("Profile Case Search")

    @json_error
    @cls_require_superuser_or_contractor
    def post(self, request, *args, **kwargs):
        data = json.loads(request.POST.get('q'))
        request_dict = data.get('request_dict', data)
        app_id = data.get('app_id', request.POST.get('app_id'))  # may be in either place
        start = datetime.now()
        config = extract_search_request_config(request_dict)
        timing_context, primary_count, related_count = profile_case_search(
            self.domain, request.couch_user, app_id, config)
        runtime = (datetime.now() - start).total_seconds()
        return json_response({
            'primary_count': primary_count,
            'related_count': related_count,
            'runtime': runtime,
            'timing_data': timing_context.to_dict(),
        })
