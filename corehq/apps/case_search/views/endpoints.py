import json

from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.case_search.endpoint_capability import get_capability
from corehq.apps.case_search.endpoint_service import (
    create_endpoint,
    deactivate_endpoint,
    get_endpoint,
    get_version,
    list_endpoints,
    save_new_version,
    validate_filter_spec,
)
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView

_ENDPOINT_DECORATORS = [
    use_bootstrap5,
    toggles.CASE_SEARCH_ENDPOINTS.required_decorator(),
]


class CaseSearchEndpointMixin:
    """Shared setup for case search endpoint views."""

    @property
    def capability(self):
        if not hasattr(self, '_capability'):
            self._capability = get_capability(self.domain)
        return self._capability

    @property
    def endpoint_obj(self):
        if not hasattr(self, '_endpoint_obj'):
            self._endpoint_obj = get_endpoint(
                self.domain, self.kwargs['endpoint_id']
            )
        return self._endpoint_obj


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointsView(BaseProjectDataView):
    urlname = 'case_search_endpoints'
    page_title = gettext_lazy('Case Search Endpoints')
    template_name = 'case_search/endpoint_list.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {
            'endpoints': list_endpoints(self.domain),
        }


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointNewView(CaseSearchEndpointMixin, BaseProjectDataView):
    urlname = 'case_search_endpoint_new'
    page_title = gettext_lazy('New Case Search Endpoint')
    template_name = 'case_search/endpoint_edit.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def parent_pages(self):
        return [{
            'title': CaseSearchEndpointsView.page_title,
            'url': reverse(CaseSearchEndpointsView.urlname, args=[self.domain]),
        }]

    @property
    def page_context(self):
        return {
            'capability': self.capability,
            'mode': 'new',
            'initial_parameters': [],
            'initial_query': {'type': 'and', 'children': []},
            'initial_target_name': '',
            'initial_name': '',
            'versions': [],
            'post_url': reverse(self.urlname, args=[self.domain]),
        }

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'errors': ['Invalid JSON']}, status=400)

        name = data.get('name', '').strip()
        target_type = data.get('target_type', 'project_db')
        target_name = data.get('target_name', '').strip()
        parameters = data.get('parameters', [])
        query = data.get('query', {'type': 'and', 'children': []})

        errors = []
        if not name:
            errors.append('Name is required.')
        if not target_name:
            errors.append('Case type is required.')

        spec_errors = validate_filter_spec(
            query, self.capability, target_name, parameters
        )
        errors.extend(spec_errors)

        if errors:
            return JsonResponse({'errors': errors}, status=400)

        endpoint = create_endpoint(
            domain=self.domain,
            name=name,
            target_type=target_type,
            target_name=target_name,
            parameters=parameters,
            query=query,
        )
        return JsonResponse({
            'redirect': reverse(
                CaseSearchEndpointEditView.urlname,
                args=[self.domain, endpoint.id],
            ),
        })


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointEditView(CaseSearchEndpointMixin, BaseProjectDataView):
    urlname = 'case_search_endpoint_edit'
    page_title = gettext_lazy('Edit Case Search Endpoint')
    template_name = 'case_search/endpoint_edit.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['endpoint_id']])

    @property
    def parent_pages(self):
        return [{
            'title': CaseSearchEndpointsView.page_title,
            'url': reverse(CaseSearchEndpointsView.urlname, args=[self.domain]),
        }]

    def _get_display_version(self):
        version_param = self.request.GET.get('version')
        if version_param:
            try:
                return get_version(self.endpoint_obj, int(version_param))
            except (ValueError, Http404):
                pass
        return self.endpoint_obj.current_version

    @property
    def page_context(self):
        version = self._get_display_version()
        is_current = (
            version and self.endpoint_obj.current_version
            and version.pk == self.endpoint_obj.current_version.pk
        )
        all_versions = list(
            self.endpoint_obj.versions.values_list('version_number', flat=True)
        )
        return {
            'capability': self.capability,
            'mode': 'edit' if is_current else 'readonly',
            'endpoint': self.endpoint_obj,
            'version': version,
            'initial_parameters': version.parameters if version else [],
            'initial_query': version.query if version else {'type': 'and', 'children': []},
            'initial_target_name': self.endpoint_obj.target_name,
            'initial_name': self.endpoint_obj.name,
            'versions': all_versions,
            'current_version_number': (
                self.endpoint_obj.current_version.version_number
                if self.endpoint_obj.current_version else None
            ),
            'display_version_number': version.version_number if version else None,
            'post_url': reverse(
                self.urlname, args=[self.domain, self.endpoint_obj.id]
            ),
        }

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'errors': ['Invalid JSON']}, status=400)

        parameters = data.get('parameters', [])
        query = data.get('query', {'type': 'and', 'children': []})

        errors = validate_filter_spec(
            query, self.capability, self.endpoint_obj.target_name, parameters
        )
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        version = save_new_version(self.endpoint_obj, parameters, query)
        return JsonResponse({
            'redirect': reverse(
                self.urlname, args=[self.domain, self.endpoint_obj.id]
            ),
            'version_number': version.version_number,
        })


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointDeactivateView(CaseSearchEndpointMixin, BaseProjectDataView):
    urlname = 'case_search_endpoint_deactivate'
    http_method_names = ['post']

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['endpoint_id']])

    def post(self, request, *args, **kwargs):
        deactivate_endpoint(self.endpoint_obj)
        return JsonResponse({
            'redirect': reverse(
                CaseSearchEndpointsView.urlname, args=[self.domain]
            ),
        })


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchCapabilityView(CaseSearchEndpointMixin, BaseProjectDataView):
    urlname = 'case_search_capability'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def get(self, request, *args, **kwargs):
        return JsonResponse(self.capability)
