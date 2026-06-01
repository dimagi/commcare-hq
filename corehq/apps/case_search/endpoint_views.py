import json

from django import forms
from django.db import transaction
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


class CaseSearchEndpointForm(forms.Form):
    name = forms.CharField()
    target_type = forms.ChoiceField(choices=CaseSearchEndpoint.TargetType.choices)
    case_type = forms.CharField(required=False)
    query = forms.CharField(required=False, widget=forms.Textarea)
    parameters = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, domain, exclude_pk=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.exclude_pk = exclude_pk

    def clean_name(self):
        name = self.cleaned_data['name']
        qs = CaseSearchEndpoint.objects.filter(domain=self.domain, name=name)
        if self.exclude_pk:
            qs = qs.exclude(pk=self.exclude_pk)
        if qs.exists():
            raise forms.ValidationError(f"An endpoint named '{name}' already exists in this project.")
        return name

    def clean_query(self):
        raw = (self.cleaned_data.get('query') or '').strip() or '{}'
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raise forms.ValidationError("Must be valid JSON.")
        if not isinstance(data, dict):
            raise forms.ValidationError("Must be a JSON object.")
        return data

    def clean_parameters(self):
        raw = (self.cleaned_data.get('parameters') or '').strip() or '[]'
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raise forms.ValidationError("Must be valid JSON.")
        if not isinstance(data, list):
            raise forms.ValidationError("Must be a JSON array.")
        return data


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
class CaseSearchEndpointNewView(BaseProjectDataView):
    urlname = 'case_search_endpoint_new'
    page_title = gettext_lazy('New Case Search Endpoint')
    template_name = 'case_search/endpoint_edit.html'

    @property
    def parent_pages(self):
        return [{'title': CaseSearchEndpointsView.page_title,
                 'url': reverse(CaseSearchEndpointsView.urlname, args=[self.domain])}]

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def _make_form(self, data=None):
        initial = {'query': '{}', 'parameters': '[]'}
        return CaseSearchEndpointForm(data, domain=self.domain, initial=initial)

    @property
    def page_context(self):
        return {
            'post_url': reverse(self.urlname, args=[self.domain]),
            'endpoint': None,
            'version_display': '',
            'form': self._form,
            'case_type_names': _get_case_type_names(self.domain),
        }

    def get(self, request, *args, **kwargs):
        self._form = self._make_form()
        return self.render_to_response(self.get_context_data())

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
            version = CaseSearchEndpointVersion.objects.create(
                endpoint=endpoint,
                version_number=1,
                query=cd['query'],
                parameters=cd['parameters'],
            )
            endpoint.current_version = version
            endpoint.save(update_fields=['current_version'])
        return redirect(reverse(CaseSearchEndpointEditView.urlname, args=[self.domain, endpoint.id]))


@method_decorator(_ENDPOINT_DECORATORS, name='dispatch')
class CaseSearchEndpointEditView(BaseProjectDataView):
    urlname = 'case_search_endpoint_edit'
    page_title = gettext_lazy('Edit Case Search Endpoint')
    template_name = 'case_search/endpoint_edit.html'

    def dispatch(self, request, *args, **kwargs):
        self._endpoint = _get_endpoint(self.domain, kwargs['endpoint_id'])
        if self._endpoint is None:
            return not_found(request)
        return super().dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{'title': CaseSearchEndpointsView.page_title,
                 'url': reverse(CaseSearchEndpointsView.urlname, args=[self.domain])}]

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self._endpoint.id])

    def _make_form(self, data=None):
        current = self._endpoint.current_version
        initial = {
            'name': self._endpoint.name,
            'target_type': self._endpoint.target_type,
            'case_type': self._endpoint.target_name,
            'query': json.dumps(current.query, indent=2) if current else '{}',
            'parameters': json.dumps(current.parameters, indent=2) if current else '[]',
        }
        return CaseSearchEndpointForm(data, domain=self.domain, exclude_pk=self._endpoint.pk, initial=initial)

    @property
    def page_context(self):
        current = self._endpoint.current_version
        return {
            'post_url': reverse(self.urlname, args=[self.domain, self._endpoint.id]),
            'endpoint': self._endpoint,
            'version_display': f'v{current.version_number}' if current else 'v1',
            'form': self._form,
            'case_type_names': _get_case_type_names(self.domain),
        }

    def get(self, request, *args, **kwargs):
        self._form = self._make_form()
        return self.render_to_response(self.get_context_data())

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
            endpoint.save(update_fields=['name', 'target_type', 'target_name'])

            current = endpoint.current_version
            next_num = (current.version_number + 1) if current else 1
            version = CaseSearchEndpointVersion.objects.create(
                endpoint=endpoint,
                version_number=next_num,
                query=cd['query'],
                parameters=cd['parameters'],
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
