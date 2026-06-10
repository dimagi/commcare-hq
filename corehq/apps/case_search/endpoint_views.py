import json

from django import forms
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.case_search.endpoint_capability import (
    MAX_QUERY_DEPTH,
    get_capability,
    validate_filter_spec,
)
from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import not_found
from corehq.apps.settings.views import BaseProjectDataView

_ENDPOINT_DECORATORS = [
    use_bootstrap5,
    toggles.CASE_SEARCH_ENDPOINTS.required_decorator(),
]

EMPTY_QUERY = {'type': 'all', 'children': []}


def _get_endpoint(domain, endpoint_id):
    return (
        CaseSearchEndpoint.objects.select_related('current_version')
        .filter(pk=endpoint_id, domain=domain, is_active=True)
        .first()
    )


def _add_endpoint_version(endpoint, *, action, created_by, query=None, parameters=None,
                          extra_update_fields=()):
    """Create the next version for ``endpoint`` and make it the current version.

    Must be called within a transaction. ``extra_update_fields`` are saved on the
    endpoint alongside ``current_version`` (e.g. fields the caller also changed).
    """
    current = endpoint.current_version
    next_num = (current.version_number + 1) if current else 1
    version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=next_num,
        query=query,
        parameters=parameters,
        created_by=created_by,
        action=action,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version', *extra_update_fields])
    return version


class CaseSearchEndpointForm(forms.Form):
    name = forms.CharField()
    target_type = forms.ChoiceField(
        choices=CaseSearchEndpoint.TargetType.choices
    )
    case_type = forms.CharField(required=False)
    query = forms.CharField(required=False, widget=forms.Textarea)
    parameters = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, domain, exclude_pk=None, capability=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.exclude_pk = exclude_pk
        self.capability = capability

    def clean_name(self):
        name = self.cleaned_data['name']
        qs = CaseSearchEndpoint.objects.filter(domain=self.domain, name=name)
        if self.exclude_pk:
            qs = qs.exclude(pk=self.exclude_pk)
        if qs.exists():
            raise forms.ValidationError(
                f"An endpoint named '{name}' already exists in this project."
            )
        return name

    def clean_query(self):
        raw = (self.cleaned_data.get('query') or '').strip() or json.dumps(
            EMPTY_QUERY
        )
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raise forms.ValidationError('Must be valid JSON.')
        if not isinstance(data, dict):
            raise forms.ValidationError('Must be a JSON object.')
        return data

    def clean_parameters(self):
        raw = (self.cleaned_data.get('parameters') or '').strip() or '[]'
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raise forms.ValidationError('Must be valid JSON.')
        if not isinstance(data, list):
            raise forms.ValidationError('Must be a JSON array.')
        return data

    def clean(self):
        cleaned = super().clean()
        query = cleaned.get('query')
        parameters = cleaned.get('parameters')
        # Only run semantic validation when both fields parsed cleanly.
        if query is not None and parameters is not None:
            capability = self.capability or get_capability(self.domain)
            for error in validate_filter_spec(
                query, cleaned.get('case_type') or '', capability
            ):
                self.add_error(None, error)
        return cleaned


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
                domain=self.domain,
                is_active=True,
            )
            .select_related('current_version')
            .order_by('name'),
        }


class _CaseSearchEndpointEditBaseView(BaseProjectDataView):
    """Shared logic for the new and edit endpoint query builder views."""

    template_name = 'case_search/endpoint_edit.html'
    mode = None

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

    @cached_property
    def capability(self):
        return get_capability(self.domain)

    def _make_form(self, data=None):
        raise NotImplementedError

    def _default_initial(self):
        """Initial query builder state for an unbound (GET) form."""
        raise NotImplementedError

    def _posted_json(self, field, default):
        if field in self._form.cleaned_data:
            return self._form.cleaned_data[field]
        raw = self._form.data.get(field)
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                pass
        return default

    def _initial_values(self):
        """Seed the query builder: defaults on GET, submitted values on a
        failed POST so the user's work survives re-render."""
        if self.request.method == 'POST':
            data = self._form.data
            return {
                'initial_name': data.get('name', ''),
                'initial_target_type': data.get(
                    'target_type', CaseSearchEndpoint.TargetType.PROJECT_DB
                ),
                'initial_target_name': data.get('case_type', ''),
                'initial_parameters': self._posted_json('parameters', []),
                'initial_query': self._posted_json('query', dict(EMPTY_QUERY)),
            }
        return self._default_initial()

    @property
    def page_context(self):
        context = {
            'capability': self.capability,
            'endpoint_mode': self.mode,
            'max_group_depth': MAX_QUERY_DEPTH - 1,
            'post_url': self.page_url,
            'form': self._form,
        }
        context.update(self._initial_values())
        return context

    def get(self, request, *args, **kwargs):
        self._form = self._make_form()
        return self.render_to_response(self.get_context_data())


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointNewView(_CaseSearchEndpointEditBaseView):
    urlname = 'case_search_endpoint_new'
    page_title = gettext_lazy('New Case Search Endpoint')
    mode = 'new'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def _make_form(self, data=None):
        return CaseSearchEndpointForm(data, domain=self.domain, capability=self.capability)

    def _default_initial(self):
        return {
            'initial_name': '',
            'initial_target_type': CaseSearchEndpoint.TargetType.PROJECT_DB,
            'initial_target_name': '',
            'initial_parameters': [],
            'initial_query': dict(EMPTY_QUERY),
        }

    def post(self, request, *args, **kwargs):
        self._form = self._make_form(request.POST)
        if not self._form.is_valid():
            return self.render_to_response(self.get_context_data())
        cd = self._form.cleaned_data
        with transaction.atomic():
            endpoint = CaseSearchEndpoint.objects.create(
                domain=self.domain,
                name=cd['name'],
                target_type=cd['target_type'],
                target_name=cd['case_type'],
            )
            _add_endpoint_version(
                endpoint,
                action=CaseSearchEndpointVersion.Action.CREATE,
                created_by=request.couch_user.username,
                query=cd['query'],
                parameters=cd['parameters'],
            )
        return redirect(
            reverse(
                CaseSearchEndpointEditView.urlname,
                args=[self.domain, endpoint.id],
            )
        )


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointEditView(_CaseSearchEndpointEditBaseView):
    urlname = 'case_search_endpoint_edit'
    page_title = gettext_lazy('Edit Case Search Endpoint')
    mode = 'edit'

    def dispatch(self, request, *args, **kwargs):
        self._endpoint = _get_endpoint(self.domain, kwargs['endpoint_id'])
        if self._endpoint is None:
            return not_found(request)
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self._endpoint.id])

    def _make_form(self, data=None):
        return CaseSearchEndpointForm(
            data, domain=self.domain, exclude_pk=self._endpoint.pk,
            capability=self.capability,
        )

    def _default_initial(self):
        current = self._endpoint.current_version
        return {
            'initial_name': self._endpoint.name,
            'initial_target_type': self._endpoint.target_type,
            'initial_target_name': self._endpoint.target_name,
            'initial_parameters': current.parameters if current else [],
            'initial_query': current.query if current else dict(EMPTY_QUERY),
        }

    @property
    def page_context(self):
        context = super().page_context
        context['endpoint'] = self._endpoint
        return context

    def post(self, request, *args, **kwargs):
        self._form = self._make_form(request.POST)
        if not self._form.is_valid():
            return self.render_to_response(self.get_context_data())
        cd = self._form.cleaned_data
        endpoint = self._endpoint
        with transaction.atomic():
            endpoint.name = cd['name']
            endpoint.target_type = cd['target_type']
            endpoint.target_name = cd['case_type']
            _add_endpoint_version(
                endpoint,
                action=CaseSearchEndpointVersion.Action.UPDATE,
                created_by=request.couch_user.username,
                query=cd['query'],
                parameters=cd['parameters'],
                extra_update_fields=['name', 'target_type', 'target_name'],
            )
        return redirect(
            reverse(CaseSearchEndpointsView.urlname, args=[self.domain])
        )


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointDeactivateView(BaseDomainView):
    urlname = 'case_search_endpoint_deactivate'
    http_method_names = ['post']

    @property
    def page_url(self):
        return reverse(
            self.urlname, args=[self.domain, self.kwargs['endpoint_id']]
        )

    def post(self, request, *args, **kwargs):
        endpoint = _get_endpoint(self.domain, kwargs['endpoint_id'])
        if endpoint is None:
            return not_found(request)
        with transaction.atomic():
            endpoint.is_active = False
            _add_endpoint_version(
                endpoint,
                action=CaseSearchEndpointVersion.Action.DEACTIVATE,
                created_by=request.couch_user.username,
                extra_update_fields=['is_active'],
            )
        return redirect(
            reverse(CaseSearchEndpointsView.urlname, args=[self.domain])
        )
