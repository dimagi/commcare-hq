import json

from django import forms
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy

from corehq import toggles
from corehq.apps.document_templates.models import Template
from corehq.apps.document_templates.rendering import (
    DocumentRenderError,
    get_preview_context,
    get_variable_names,
    render_template,
)
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.sms.views import BaseMessagingSectionView


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class DocumentTemplatesView(BaseMessagingSectionView):
    urlname = 'document_templates'
    page_title = gettext_lazy('Document Templates')
    template_name = 'document_templates/template_list.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {
            'templates': Template.objects.filter(
                domain=self.domain,
            )
            .order_by('name')
        }


VARIABLE_FIELD_PREFIX = 'var_'


class TemplateForm(forms.Form):
    name = forms.CharField(max_length=255)
    slug = forms.SlugField(max_length=50)

    def __init__(self, *args, variable_names, existing_slugs=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.variable_names = variable_names
        self.existing_slugs = set(existing_slugs)
        for variable_name in variable_names:
            self.fields[self._field_name(variable_name)] = forms.CharField(
                label=variable_name,
                required=False,
                widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            )

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if slug in self.existing_slugs:
            raise forms.ValidationError(gettext('A template with this slug already exists.'))
        return slug

    @staticmethod
    def _field_name(variable_name):
        return f'{VARIABLE_FIELD_PREFIX}{variable_name}'

    @classmethod
    def initial_from_template(cls, template, variable_names):
        initial = {'name': template.name, 'slug': template.slug}
        for variable_name in variable_names:
            variable = template.variables.get(variable_name, {})
            initial[cls._field_name(variable_name)] = variable.get('value', '')
        return initial

    def variable_fields(self):
        return [self[self._field_name(name)] for name in self.variable_names]

    def get_variables(self):
        return {
            variable_name: {
                'type': 'markdown',
                'value': self.cleaned_data[self._field_name(variable_name)],
            }
            for variable_name in self.variable_names
        }


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class NewDocumentTemplateView(BaseMessagingSectionView):
    urlname = 'new_document_template'
    page_title = gettext_lazy('New Template')
    template_name = 'document_templates/template_form.html'
    initial = None

    @cached_property
    def form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return TemplateForm(
            data,
            variable_names=get_variable_names(),
            existing_slugs=self.get_existing_slugs(),
            initial=self.initial,
        )

    def get_existing_slugs(self):
        return Template.objects.filter(domain=self.domain).values_list('slug', flat=True)

    @property
    def page_context(self):
        return {'form': self.form}

    def save_template(self):
        return Template.objects.create(
            domain=self.domain,
            name=self.form.cleaned_data['name'],
            slug=self.form.cleaned_data['slug'],
            variables=self.form.get_variables(),
        )

    def post(self, request, *args, **kwargs):
        if not self.form.is_valid():
            return self.get(request, *args, **kwargs)

        self.save_template()
        return HttpResponseRedirect(
            reverse(DocumentTemplatesView.urlname, args=[self.domain])
        )


class EditDocumentTemplateView(NewDocumentTemplateView):
    urlname = 'edit_document_template'
    page_title = gettext_lazy('Edit Document Template')

    @cached_property
    def document_template(self):
        return get_object_or_404(Template, domain=self.domain, pk=self.kwargs['template_id'])

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.document_template.pk])

    def get_existing_slugs(self):
        return super().get_existing_slugs().exclude(pk=self.document_template.pk)

    @property
    def initial(self):
        return TemplateForm.initial_from_template(self.document_template, get_variable_names())

    def save_template(self):
        template = self.document_template
        template.name = self.form.cleaned_data['name']
        template.slug = self.form.cleaned_data['slug']
        template.variables = self.form.get_variables()
        template.save()
        return template


@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class DeleteDocumentTemplateView(BaseMessagingSectionView):
    urlname = 'delete_document_template'
    http_method_names = ['post']

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['template_id']])

    def post(self, request, *args, **kwargs):
        template = get_object_or_404(Template, domain=self.domain, pk=kwargs['template_id'])
        template.delete()
        return HttpResponseRedirect(
            reverse(DocumentTemplatesView.urlname, args=[self.domain])
        )


def _posted_variable_values(request):
    """The variable values of the template form, as posted (the rest of the form is ignored)"""
    return {
        name: request.POST.get(f'{VARIABLE_FIELD_PREFIX}{name}', '')
        for name in get_variable_names()
    }


@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class PreviewVariablesView(BaseMessagingSectionView):
    """HTMX partial for the preview modal: the context the posted values need"""

    urlname = 'preview_document_variables'
    http_method_names = ['post']
    template_name = 'document_templates/partials/preview_modal_body.html'

    def post(self, request, *args, **kwargs):
        try:
            context = get_preview_context(_posted_variable_values(request))
        except DocumentRenderError as error:
            template_context = {'error': str(error)}
        else:
            template_context = {'context_json': json.dumps(context, indent=2)}
        return HttpResponse(render_to_string(self.template_name, template_context))


@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class PreviewDocumentView(BaseMessagingSectionView):
    """The rendered document, for opening in a new tab"""

    urlname = 'preview_document'
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        try:
            context = json.loads(request.POST.get('context') or '{}')
            if not isinstance(context, dict):
                raise ValueError(gettext('The context must be a JSON object.'))
            html = render_template(_posted_variable_values(request), context)
        except (ValueError, DocumentRenderError) as error:
            return HttpResponseBadRequest(format_html('<pre>{}</pre>', error))
        response = HttpResponse(html)
        # The document needs no scripts; a sandboxed document cannot run any
        response['Content-Security-Policy'] = 'sandbox'
        return response
