from io import BytesIO

from django import forms
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic.edit import ModelFormMixin, ProcessFormView

from corehq import toggles
from corehq.apps.document_templates.models import Area, Template
from corehq.apps.document_templates.rendering import (
    DocumentRenderError,
    get_area_names,
    generate_document,
    get_variable_names,
    render_pdf,
)
from corehq.apps.domain.decorators import login_and_domain_required
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
                deleted=False,
            )
            .order_by('name')
        }


AREA_FIELD_PREFIX = 'area_'
CONTEXT_FIELD_PREFIX = 'context_'


class TemplateForm(forms.ModelForm):
    class Meta:
        model = Template
        fields = ['name', 'slug']

    def __init__(self, *args, domain, area_names, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.domain = domain
        self.area_names = area_names
        saved_areas = self.instance.areas or {}
        for area_name in area_names:
            area = saved_areas.get(area_name)
            self.fields[self._field_name(area_name)] = forms.CharField(
                label=area_name,
                required=False,
                initial=area.value if area else '',
                widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            )

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        others = Template.objects.filter(
            domain=self.instance.domain, slug=slug, deleted=False,
        ).exclude(pk=self.instance.pk)
        if others.exists():
            raise forms.ValidationError(gettext('A template with this slug already exists.'))
        return slug

    @staticmethod
    def _field_name(area_name):
        return f'{AREA_FIELD_PREFIX}{area_name}'

    def area_fields(self):
        return [self[self._field_name(name)] for name in self.area_names]

    def get_areas(self):
        return {
            area_name: Area(value=self.cleaned_data[self._field_name(area_name)])
            for area_name in self.area_names
        }

    def save(self, commit=True):
        self.instance.areas = self.get_areas()
        return super().save(commit=commit)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class BaseDocumentTemplateFormView(BaseMessagingSectionView, ModelFormMixin, ProcessFormView):
    template_name = 'document_templates/template_form.html'
    form_class = TemplateForm

    def get_queryset(self):
        return Template.objects.filter(domain=self.domain, deleted=False)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        kwargs['area_names'] = get_area_names()
        return kwargs

    def get_success_url(self):
        return reverse(DocumentTemplatesView.urlname, args=[self.domain])


class NewDocumentTemplateView(BaseDocumentTemplateFormView):
    urlname = 'new_document_template'
    page_title = gettext_lazy('New Template')

    def get(self, request, *args, **kwargs):
        self.object = None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = None
        return super().post(request, *args, **kwargs)


class EditDocumentTemplateView(BaseDocumentTemplateFormView):
    urlname = 'edit_document_template'
    page_title = gettext_lazy('Edit Document Template')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['pk']])

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)


@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class DeleteDocumentTemplateView(BaseMessagingSectionView):
    urlname = 'delete_document_template'
    http_method_names = ['post']

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['pk']])

    def post(self, request, *args, **kwargs):
        template = get_object_or_404(Template, domain=self.domain, pk=kwargs['pk'], deleted=False)
        template.deleted = True
        template.save(update_fields=['deleted'])
        return HttpResponseRedirect(
            reverse(DocumentTemplatesView.urlname, args=[self.domain])
        )


def _posted_areas(request):
    """The areas of the template form, as posted (the rest of the form is ignored)"""
    return {
        name: Area(value=request.POST.get(f'{AREA_FIELD_PREFIX}{name}', ''))
        for name in get_area_names()
    }


def _posted_context(request, names):
    """The values posted for the variables ``names``; unfilled variables are empty"""
    return {name: request.POST.get(f'{CONTEXT_FIELD_PREFIX}{name}', '') for name in names}


@login_and_domain_required
@toggles.DOCUMENT_TEMPLATES.required_decorator()
@require_POST
def preview_document_variables(request, domain):
    """HTMX partial for the preview modal: an input for each variable the posted areas use

    The form is posted with the request, so values already typed into the modal are kept.
    """
    try:
        names = get_variable_names(_posted_areas(request))
    except DocumentRenderError as error:
        template_context = {'error': str(error)}
    else:
        template_context = {'context': _posted_context(request, names), 'field_prefix': CONTEXT_FIELD_PREFIX}
    return HttpResponse(render_to_string('document_templates/partials/preview_modal_body.html', template_context))


@login_and_domain_required
@toggles.DOCUMENT_TEMPLATES.required_decorator()
@require_POST
def preview_document(request, domain):
    """The rendered document as a PDF, for opening in a new tab"""
    areas = _posted_areas(request)
    try:
        context = _posted_context(request, get_variable_names(areas))
        pdf = render_pdf([generate_document(areas, context)])
    except DocumentRenderError as error:
        return HttpResponseBadRequest(format_html('<pre>{}</pre>', error))
    response = FileResponse(BytesIO(pdf), filename='preview.pdf')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
