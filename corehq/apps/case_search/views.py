import json
import re
from io import BytesIO

from django.http import Http404, HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.apps.case_search.forms import CSQLFixtureExpressionForm
from corehq.apps.case_search.models import (
    CSQLFixtureExpression,
    case_search_enabled_for_domain,
)
from corehq.apps.case_search.utils import get_case_search_results_from_request
from corehq.apps.domain.decorators import cls_require_superuser_or_contractor
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqadmin.utils import get_download_url
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView
from corehq.util.dates import get_timestamp_for_filename
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
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


@method_decorator(use_bootstrap5, name='dispatch')
class CaseSearchView(_BaseCaseSearchView):
    template_name = 'case_search/case_search.html'
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
            value = re.sub(re.escape(param.get('regex', '')), '', param.get('value'))
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


@method_decorator(use_bootstrap5, name='dispatch')
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
        _, profiler = get_case_search_results_from_request(
            self.domain, app_id, request.couch_user, request_dict, debug=True)
        return json_response({
            'primary_count': profiler.primary_count,
            'related_count': profiler.related_count,
            'timing_data': profiler.timing_context.to_dict(),
            'queries': [self._make_profile_downloadable(q) for q in profiler.queries],
        })

    @staticmethod
    def _make_profile_downloadable(query):
        profile_json = query.pop('profile_json')
        timestamp = get_timestamp_for_filename()
        name = f"es_profile_{query['query_number']}_{query['slug']}_{timestamp}.json"
        io = BytesIO()
        io.write(json.dumps(profile_json).encode('utf-8'))
        io.seek(0)
        query['profile_url'] = get_download_url(io, name, content_type='application/json')
        return query


@method_decorator([
    use_bootstrap5,
    toggles.CSQL_FIXTURE.required_decorator(),
    require_can_edit_data,
], name='dispatch')
class CSQLFixtureExpressionView(HqHtmxActionMixin, BaseProjectDataView):
    urlname = 'csql_fixture_configuration'
    page_title = gettext_lazy('CSQL Fixture Configuration')
    template_name = 'case_search/csql_fixture_configuration.html'

    @property
    def page_context(self):
        expressions = CSQLFixtureExpression.by_domain(self.domain)
        return {'csql_fixture_forms': [
            CSQLFixtureExpressionForm(self.domain, instance=expression) for expression in expressions
        ]}

    @hq_hx_action('post')
    def new_expression(self, *args, **kwargs):
        return HttpResponse(CSQLFixtureExpressionForm(self.domain).render())

    @hq_hx_action('post')
    def save_expression(self, request, domain, *args, **kwargs):
        if pk := request.POST.get('pk'):
            expression = CSQLFixtureExpression.objects.get(domain=domain, pk=pk)
        else:
            expression = None
        form = CSQLFixtureExpressionForm(self.domain, request.POST, instance=expression)
        if form.is_valid():
            form.save()
            return HttpResponse(form.render())
        raise AssertionError("The user shouldn't be able to submit an invalid form")

    @hq_hx_action('post')
    def delete_expression(self, request, domain, *args, **kwargs):
        if pk := request.POST.get('pk'):
            CSQLFixtureExpression.objects.get(domain=domain, pk=pk).soft_delete()
        return self.render_htmx_no_response(request)
