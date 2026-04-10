import json

from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.case_search.endpoint_capability import get_capability
from corehq.apps.case_search.endpoint_service import (
    FilterSpecValidationError,
    create_endpoint,
    deactivate_endpoint,
    get_endpoint,
    get_version,
    list_endpoints,
    save_new_version,
)
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView

_ENDPOINT_DECORATORS = [
    use_bootstrap5,
    toggles.CASE_SEARCH_ENDPOINTS.required_decorator(),
]


class CaseSearchEndpointMixin:
    """Shared helpers for endpoint views."""

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
        return {'endpoints': list_endpoints(self.domain)}


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
        return [
            {
                'title': CaseSearchEndpointsView.page_title,
                'url': reverse(
                    CaseSearchEndpointsView.urlname, args=[self.domain]
                ),
            }
        ]

    @property
    def page_context(self):
        return {
            'capability': self.capability,
            'mode': 'new',
            'initial_name': '',
            'initial_target_name': '',
            'initial_parameters': [],
            'initial_query': {'type': 'and', 'children': []},
            'post_url': reverse(self.urlname, args=[self.domain]),
        }

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'errors': ['Invalid JSON']}, status=400)
        try:
            endpoint = create_endpoint(
                domain=self.domain,
                name=data.get('name', ''),
                target_type=data.get('target_type', 'project_db'),
                target_name=data.get('target_name', ''),
                parameters=data.get('parameters', []),
                query=data.get('query', {'type': 'and', 'children': []}),
            )
        except FilterSpecValidationError as e:
            return JsonResponse({'errors': e.errors}, status=400)
        return JsonResponse(
            {
                'redirect': reverse(
                    CaseSearchEndpointEditView.urlname,
                    args=[self.domain, endpoint.id],
                ),
            }
        )


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointEditView(CaseSearchEndpointMixin, BaseProjectDataView):
    urlname = 'case_search_endpoint_edit'
    page_title = gettext_lazy('Edit Case Search Endpoint')
    template_name = 'case_search/endpoint_edit.html'

    @property
    def page_url(self):
        return reverse(
            self.urlname, args=[self.domain, self.kwargs['endpoint_id']]
        )

    @property
    def parent_pages(self):
        return [
            {
                'title': CaseSearchEndpointsView.page_title,
                'url': reverse(
                    CaseSearchEndpointsView.urlname, args=[self.domain]
                ),
            }
        ]

    @property
    def page_context(self):
        endpoint = self.endpoint_obj
        current_version = endpoint.current_version
        all_versions = list(
            endpoint.versions.values_list('version_number', flat=True)
        )
        versions_with_urls = [
            {
                'number': v,
                'url': reverse(self.urlname, args=[self.domain, endpoint.id])
                if v == current_version.version_number
                else reverse(
                    CaseSearchEndpointVersionView.urlname,
                    args=[self.domain, endpoint.id, v],
                ),
                'is_current': v == current_version.version_number,
            }
            for v in all_versions
        ]
        return {
            'capability': self.capability,
            'mode': 'edit',
            'endpoint': endpoint,
            'initial_name': endpoint.name,
            'initial_target_name': endpoint.target_name,
            'initial_parameters': current_version.parameters,
            'initial_query': current_version.query,
            'post_url': reverse(self.urlname, args=[self.domain, endpoint.id]),
            'display_version_number': current_version.version_number,
            'current_version_number': current_version.version_number,
            'versions_with_urls': versions_with_urls,
        }

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'errors': ['Invalid JSON']}, status=400)
        try:
            version = save_new_version(
                self.endpoint_obj,
                parameters=data.get('parameters', []),
                query=data.get('query', {'type': 'and', 'children': []}),
            )
        except FilterSpecValidationError as e:
            return JsonResponse({'errors': e.errors}, status=400)
        return JsonResponse(
            {
                'version_number': version.version_number,
                'redirect': reverse(
                    self.urlname, args=[self.domain, self.endpoint_obj.id]
                ),
            }
        )


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointVersionView(
    CaseSearchEndpointMixin, BaseProjectDataView
):
    urlname = 'case_search_endpoint_version'
    page_title = gettext_lazy('Endpoint Version')
    template_name = 'case_search/endpoint_edit.html'

    @property
    def page_url(self):
        return reverse(
            self.urlname,
            args=[
                self.domain,
                self.kwargs['endpoint_id'],
                self.kwargs['version_number'],
            ],
        )

    @property
    def parent_pages(self):
        return [
            {
                'title': CaseSearchEndpointsView.page_title,
                'url': reverse(
                    CaseSearchEndpointsView.urlname, args=[self.domain]
                ),
            },
            {
                'title': self.endpoint_obj.name,
                'url': reverse(
                    CaseSearchEndpointEditView.urlname,
                    args=[self.domain, self.endpoint_obj.id],
                ),
            },
        ]

    @property
    def page_context(self):
        endpoint = self.endpoint_obj
        version = get_version(endpoint, int(self.kwargs['version_number']))
        current_version = endpoint.current_version
        all_versions = list(
            endpoint.versions.values_list('version_number', flat=True)
        )
        versions_with_urls = [
            {
                'number': v,
                'url': reverse(
                    CaseSearchEndpointEditView.urlname,
                    args=[self.domain, endpoint.id],
                )
                if v == current_version.version_number
                else reverse(self.urlname, args=[self.domain, endpoint.id, v]),
                'is_current': v == current_version.version_number,
            }
            for v in all_versions
        ]
        return {
            'capability': self.capability,
            'mode': 'readonly',
            'endpoint': endpoint,
            'initial_name': endpoint.name,
            'initial_target_name': endpoint.target_name,
            'initial_parameters': version.parameters,
            'initial_query': version.query,
            'post_url': None,
            'display_version_number': version.version_number,
            'current_version_number': current_version.version_number,
            'versions_with_urls': versions_with_urls,
        }


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointDeactivateView(CaseSearchEndpointMixin, BaseDomainView):
    urlname = 'case_search_endpoint_deactivate'
    http_method_names = ['post']

    @property
    def page_url(self):
        return reverse(
            self.urlname, args=[self.domain, self.kwargs['endpoint_id']]
        )

    def post(self, request, *args, **kwargs):
        deactivate_endpoint(self.endpoint_obj)
        return HttpResponse(status=200)


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchCapabilityView(BaseDomainView):
    urlname = 'case_search_capability'

    def get(self, request, *args, **kwargs):
        return JsonResponse(get_capability(self.domain))
