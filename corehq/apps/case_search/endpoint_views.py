import json

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.case_search.models import CaseSearchEndpoint, CaseSearchEndpointVersion
from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import not_found
from corehq.apps.settings.views import BaseProjectDataView

_ENDPOINT_DECORATORS = [
    use_bootstrap5,
    toggles.CASE_SEARCH_ENDPOINTS.required_decorator(),
]


def _get_endpoint(domain, endpoint_id):
    return CaseSearchEndpoint.objects.select_related('current_version').filter(
        pk=endpoint_id, domain=domain, is_active=True
    ).first()


def _get_case_type_names(domain):
    return list(
        CaseType.objects.filter(domain=domain, is_deprecated=False)
        .values_list('name', flat=True)
        .order_by('name')
    )


def _parse_json_object(raw):
    """Parse a JSON object from a string, returning (data, error_string)."""
    raw = (raw or '').strip() or '{}'
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None, "Query must be valid JSON."
    if not isinstance(data, dict):
        return None, "Query must be a JSON object."
    return data, None


def _parse_json_array(raw):
    """Parse a JSON array from a string, returning (data, error_string)."""
    raw = (raw or '').strip() or '[]'
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None, "Parameters must be valid JSON."
    if not isinstance(data, list):
        return None, "Parameters must be a JSON array."
    return data, None


class _EndpointFormMixin:
    """Shared form state, validation, and rendering for create/edit endpoint views."""

    template_name = 'case_search/endpoint_edit.html'

    def _init_form_state(self):
        self._errors = []
        self._name = ''
        self._target_type = CaseSearchEndpoint.TargetType.PROJECT_DB
        self._case_type = ''
        self._query_raw = '{}'
        self._parameters_raw = '[]'

    def _parse_post(self, request):
        self._name = request.POST.get('name', '').strip()
        self._target_type = request.POST.get('target_type', self._target_type)
        self._case_type = request.POST.get('case_type', '').strip()
        self._query_raw = request.POST.get('query', '{}')
        self._parameters_raw = request.POST.get('parameters', '[]')

    def _validate(self, exclude_pk=None):
        """Validate form state. Returns (errors, query, parameters)."""
        errors = []
        if not self._name:
            errors.append("Name is required.")
        else:
            qs = CaseSearchEndpoint.objects.filter(domain=self.domain, name=self._name)
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            if qs.exists():
                errors.append(f"An endpoint named '{self._name}' already exists in this project.")

        query, err = _parse_json_object(self._query_raw)
        if err:
            errors.append(err)

        parameters, err = _parse_json_array(self._parameters_raw)
        if err:
            errors.append(err)

        return errors, query, parameters

    @property
    def parent_pages(self):
        return [{'title': CaseSearchEndpointsView.page_title,
                 'url': reverse(CaseSearchEndpointsView.urlname, args=[self.domain])}]

    @property
    def _form_context(self):
        return {
            'errors': self._errors,
            'name': self._name,
            'target_type': self._target_type,
            'case_type': self._case_type,
            'query_raw': self._query_raw,
            'parameters_raw': self._parameters_raw,
            'target_type_choices': CaseSearchEndpoint.TargetType.choices,
            'case_type_names': _get_case_type_names(self.domain),
        }

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())


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
            'endpoints': CaseSearchEndpoint.objects.filter(
                domain=self.domain, is_active=True,
            ).select_related('current_version').order_by('name'),
        }


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointNewView(_EndpointFormMixin, BaseProjectDataView):
    urlname = 'case_search_endpoint_new'
    page_title = gettext_lazy('New Case Search Endpoint')

    def dispatch(self, request, *args, **kwargs):
        self._init_form_state()
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {
            'post_url': reverse(self.urlname, args=[self.domain]),
            'endpoint': None,
            **self._form_context,
        }

    def post(self, request, *args, **kwargs):
        self._parse_post(request)
        errors, query, parameters = self._validate()
        if errors:
            self._errors = errors
            return self.render_to_response(self.get_context_data())

        endpoint = CaseSearchEndpoint.objects.create(
            domain=self.domain,
            name=self._name,
            target_type=self._target_type,
            target_name=self._case_type,
        )
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=endpoint,
            version_number=1,
            query=query,
            parameters=parameters,
        )
        endpoint.current_version = version
        endpoint.save(update_fields=['current_version'])
        return redirect(reverse(CaseSearchEndpointEditView.urlname, args=[self.domain, endpoint.id]))


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointEditView(_EndpointFormMixin, BaseProjectDataView):
    urlname = 'case_search_endpoint_edit'
    page_title = gettext_lazy('Edit Case Search Endpoint')

    def dispatch(self, request, *args, **kwargs):
        self._endpoint = _get_endpoint(self.domain, kwargs['endpoint_id'])
        if self._endpoint is None:
            return not_found(request)
        self._init_form_state()
        current = self._endpoint.current_version
        self._name = self._endpoint.name
        self._target_type = self._endpoint.target_type
        self._case_type = self._endpoint.target_name
        self._query_raw = json.dumps(current.query, indent=2) if current else '{}'
        self._parameters_raw = json.dumps(current.parameters, indent=2) if current else '[]'
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self._endpoint.id])

    @property
    def page_context(self):
        return {
            'post_url': reverse(self.urlname, args=[self.domain, self._endpoint.id]),
            'endpoint': self._endpoint,
            **self._form_context,
        }

    def post(self, request, *args, **kwargs):
        self._parse_post(request)
        errors, query, parameters = self._validate(exclude_pk=self._endpoint.pk)
        if errors:
            self._errors = errors
            return self.render_to_response(self.get_context_data())

        endpoint = self._endpoint
        endpoint.name = self._name
        endpoint.target_type = self._target_type
        endpoint.target_name = self._case_type
        endpoint.save(update_fields=['name', 'target_type', 'target_name'])

        current = endpoint.current_version
        next_num = (current.version_number + 1) if current else 1
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=endpoint,
            version_number=next_num,
            query=query,
            parameters=parameters,
        )
        endpoint.current_version = version
        endpoint.save(update_fields=['current_version'])
        return redirect(reverse(CaseSearchEndpointsView.urlname, args=[self.domain]))


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointDeactivateView(BaseDomainView):
    urlname = 'case_search_endpoint_deactivate'
    http_method_names = ['post']

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['endpoint_id']])

    def post(self, request, *args, **kwargs):
        endpoint = _get_endpoint(self.domain, kwargs['endpoint_id'])
        if endpoint is None:
            return not_found(request)
        endpoint.is_active = False
        endpoint.save(update_fields=['is_active'])
        return redirect(reverse(CaseSearchEndpointsView.urlname, args=[self.domain]))
