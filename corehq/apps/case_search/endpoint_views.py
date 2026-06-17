import json

from django import forms
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.case_search.endpoint_capability import (
    get_capability,
)
from corehq.apps.case_search.endpoint_query_spec import (
    MAX_QUERY_DEPTH,
    parse_query_spec,
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

def empty_query():
    return {'type': 'all', 'children': []}


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
    query = forms.JSONField(required=False)
    parameters = forms.JSONField(required=False)

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
        data = self.cleaned_data.get('query')
        if data is None:
            return empty_query()
        if not isinstance(data, dict):
            raise forms.ValidationError('Must be a JSON object.')
        return data

    def clean_parameters(self):
        data = self.cleaned_data.get('parameters')
        if data is None:
            return []
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
            _, errors = parse_query_spec(
                query, cleaned.get('case_type') or '', capability
            )
            for error in errors:
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

    @property
    def page_context(self):
        return {
            'capability': self.capability,
            'endpoint_mode': self.mode,
            'max_group_depth': MAX_QUERY_DEPTH - 1,
            'post_url': self.page_url,
            'form': self._form,
        }

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
        return CaseSearchEndpointForm(
            data,
            domain=self.domain,
            capability=self.capability,
            initial={
                'target_type': CaseSearchEndpoint.TargetType.PROJECT_DB,
                'query': empty_query,
                'parameters': list,
            },
        )

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
        current = self._endpoint.current_version
        return CaseSearchEndpointForm(
            data,
            domain=self.domain,
            exclude_pk=self._endpoint.pk,
            capability=self.capability,
            initial={
                'name': self._endpoint.name,
                'target_type': self._endpoint.target_type,
                'case_type': self._endpoint.target_name,
                'query': current.query if current else empty_query,
                'parameters': current.parameters if current else list,
            },
        )

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


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointTestView(BaseDomainView):
    """Runs a query builder spec against the project's cases and returns an
    HTMX partial with the matching results (or validation errors).

    Domain-scoped rather than endpoint-scoped so it works for unsaved
    queries on the new-endpoint page too.
    """

    urlname = 'case_search_endpoint_test'
    http_method_names = ['post']
    _results_template = 'case_search/partials/_test_results.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def post(self, request, *args, **kwargs):
        case_type = request.POST.get('case_type', '')
        try:
            query = json.loads(request.POST.get('query') or '{}')
        except (json.JSONDecodeError, ValueError):
            return self._render_results(request, errors=['Invalid query JSON.'])
        _, errors = parse_query_spec(query, case_type, get_capability(self.domain))
        if errors:
            return self._render_results(request, errors=errors)
        columns, rows = self._run_query(case_type, query)
        return self._render_results(request, columns=columns, rows=rows)

    def _run_query(self, case_type, query):
        # TODO: translate the filter spec into a case search ES query, run it,
        # and shape the hits into columns/rows. Dummy data for now.
        columns = ['Case Name', 'Case Type', 'Owner', 'Date Opened']
        rows = [
            ['Example case 1', case_type, 'worker@example.com', '2026-01-15'],
            ['Example case 2', case_type, 'worker@example.com', '2026-02-03'],
        ]
        return columns, rows

    def _render_results(self, request, *, errors=None, columns=None, rows=None):
        # Always 200 so HTMX swaps the partial in (it ignores error statuses).
        return render(request, self._results_template, {
            'errors': errors or [],
            'columns': columns or [],
            'rows': rows or [],
        })
