from dataclasses import dataclass
from io import BytesIO

from django import forms
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
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
from corehq.apps.cloudcare.decorators import require_cloudcare_access
from corehq.apps.document_templates.case_documents import (
    CaseDocumentError,
    render_case_documents,
)
from corehq.apps.document_templates.images import (
    ImageError,
    get_image,
    get_image_data,
    get_thumbnail_url,
    save_image,
)
from corehq.apps.document_templates.models import (
    AREA_TYPES,
    IMAGE,
    MARKDOWN,
    Area,
    Template,
)
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
from corehq.apps.users.decorators import get_permission_name, require_permission
from corehq.apps.users.models import HqPermissions


class BaseDocumentTemplatesView(BaseMessagingSectionView):
    """Document templates sit in the messaging section but have permissions of their own

    Skips the messaging permission, privilege and access checks of
    :class:`BaseMessagingSectionView`.
    """

    def dispatch(self, request, *args, **kwargs):
        return super(BaseMessagingSectionView, self).dispatch(request, *args, **kwargs)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
@method_decorator(require_permission(HqPermissions.view_document_templates), name='dispatch')
class DocumentTemplatesView(BaseDocumentTemplatesView):
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
            .order_by('name'),
            'can_edit': self.request.couch_user.has_permission(
                self.domain, get_permission_name(HqPermissions.edit_document_templates)
            ),
        }


AREA_FIELD_PREFIX = 'area_'
CONTEXT_FIELD_PREFIX = 'context_'


@dataclass
class AreaFields:
    """What the editor shows for an area

    :param type: ``'markdown'`` or ``'image'``, to show the matching field
    :param image: the context of the image fields, see :func:`area_image_context`
    """
    name: str
    type: str
    type_field: forms.BoundField
    markdown_field: forms.BoundField
    image: dict


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
            area = saved_areas.get(area_name) or Area()
            is_image = area.type == IMAGE
            # both values are kept in the form so switching the type does not lose what was typed;
            # only the one of the selected type is saved
            self.fields[self._field_name(area_name)] = forms.CharField(
                label=area_name,
                required=False,
                initial='' if is_image else area.value,
                widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            )
            self.fields[self._type_field_name(area_name)] = forms.ChoiceField(
                choices=[(MARKDOWN, gettext_lazy('Markdown')), (IMAGE, gettext_lazy('Image'))],
                required=False,
                initial=area.type,
                widget=forms.Select(attrs={
                    'class': 'form-select',
                    'x-model': 'type',
                    'aria-label': gettext('Type of {area}').format(area=area_name),
                }),
            )
            self.fields[self._image_field_name(area_name)] = forms.CharField(
                required=False,
                initial=area.value if is_image else '',
                widget=forms.HiddenInput(),
            )

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        others = Template.objects.filter(
            domain=self.instance.domain, slug=slug, deleted=False,
        ).exclude(pk=self.instance.pk)
        if others.exists():
            raise forms.ValidationError(gettext('A template with this slug already exists.'))
        return slug

    def clean(self):
        cleaned_data = super().clean()
        for area_name in self.area_names:
            image_id = cleaned_data.get(self._image_field_name(area_name))
            if cleaned_data.get(self._type_field_name(area_name)) == IMAGE and image_id:
                try:
                    get_image(self.instance.domain, image_id)
                except ImageError as error:
                    self.add_error(self._image_field_name(area_name), str(error))
        return cleaned_data

    @staticmethod
    def _field_name(area_name):
        return f'{AREA_FIELD_PREFIX}{area_name}'

    @staticmethod
    def _type_field_name(area_name):
        return f'{AREA_FIELD_PREFIX}{area_name}_type'

    @staticmethod
    def _image_field_name(area_name):
        return f'{AREA_FIELD_PREFIX}{area_name}_image'

    def areas(self):
        """The fields of each area, for the editor"""
        return [self._area_fields(area_name) for area_name in self.area_names]

    def _area_fields(self, area_name):
        image_field = self[self._image_field_name(area_name)]
        image_id = image_field.value() or ''
        image_error = next(iter(image_field.errors), None)
        area_type = self[self._type_field_name(area_name)].value()
        return AreaFields(
            name=area_name,
            type=area_type if area_type in AREA_TYPES else MARKDOWN,
            type_field=self[self._type_field_name(area_name)],
            markdown_field=self[self._field_name(area_name)],
            image=area_image_context(self.instance.domain, area_name, image_id, image_error),
        )

    def get_areas(self):
        areas = {}
        for area_name in self.area_names:
            if self.cleaned_data[self._type_field_name(area_name)] == IMAGE:
                areas[area_name] = Area(type=IMAGE, value=self.cleaned_data[self._image_field_name(area_name)])
            else:
                areas[area_name] = Area(value=self.cleaned_data[self._field_name(area_name)])
        return areas

    def save(self, commit=True):
        self.instance.areas = self.get_areas()
        return super().save(commit=commit)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
@method_decorator(require_permission(HqPermissions.edit_document_templates), name='dispatch')
class BaseDocumentTemplateFormView(BaseDocumentTemplatesView, ModelFormMixin, ProcessFormView):
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
@method_decorator(require_permission(HqPermissions.edit_document_templates), name='dispatch')
class DeleteDocumentTemplateView(BaseDocumentTemplatesView):
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


def _posted_area_type(request, area_name):
    area_type = request.POST.get(f'{AREA_FIELD_PREFIX}{area_name}_type')
    return area_type if area_type in AREA_TYPES else MARKDOWN


def _posted_markdown_areas(request):
    """The areas that are markdown, as posted (the rest of the form is ignored)"""
    return {
        name: Area(value=request.POST.get(f'{AREA_FIELD_PREFIX}{name}', ''))
        for name in get_area_names()
        if _posted_area_type(request, name) == MARKDOWN
    }


def _posted_areas(request, domain):
    """The areas as posted, for :func:`generate_document`: the image of an image area is looked up

    :raises DocumentRenderError: if an image cannot be used
    """
    areas = {}
    for name in get_area_names():
        if _posted_area_type(request, name) == IMAGE:
            image_id = request.POST.get(f'{AREA_FIELD_PREFIX}{name}_image', '')
            try:
                value = get_image_data(domain, image_id) if image_id else b''
            except ImageError as error:
                raise DocumentRenderError(f'{name}: {error}')
            areas[name] = Area(type=IMAGE, value=value)
        else:
            areas[name] = Area(value=request.POST.get(f'{AREA_FIELD_PREFIX}{name}', ''))
    return areas


def _posted_context(request, names):
    """The values posted for the variables ``names``; unfilled variables are empty"""
    return {name: request.POST.get(f'{CONTEXT_FIELD_PREFIX}{name}', '') for name in names}


@require_permission(HqPermissions.view_document_templates)
@toggles.DOCUMENT_TEMPLATES.required_decorator()
@require_POST
def preview_document_variables(request, domain):
    """HTMX partial for the preview modal: an input for each variable the posted areas use

    The form is posted with the request, so values already typed into the modal are kept.
    """
    try:
        names = get_variable_names(_posted_markdown_areas(request))
    except DocumentRenderError as error:
        template_context = {'error': str(error)}
    else:
        template_context = {'context': _posted_context(request, names), 'field_prefix': CONTEXT_FIELD_PREFIX}
    return HttpResponse(render_to_string('document_templates/partials/preview_modal_body.html', template_context))


@require_permission(HqPermissions.view_document_templates)
@toggles.DOCUMENT_TEMPLATES.required_decorator()
@require_POST
def preview_document(request, domain):
    """The rendered document as a PDF, for opening in a new tab"""
    try:
        areas = _posted_areas(request, domain)
        context = _posted_context(request, get_variable_names(areas))
        pdf = render_pdf([generate_document(areas, context)])
    except DocumentRenderError as error:
        return HttpResponseBadRequest(format_html('<pre>{}</pre>', error))
    response = FileResponse(BytesIO(pdf), filename='preview.pdf')
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_and_domain_required
@require_cloudcare_access
@toggles.DOCUMENT_TEMPLATES.required_decorator()
@require_POST
def render_document(request, domain):
    """Called from web apps with space separated case IDs as the request body

    Responds with a PDF with a document for each case.
    """
    try:
        pdf = render_case_documents(domain, request.body.decode().split(), request.couch_user)
    except CaseDocumentError:
        return JsonResponse(
            {'error': gettext('Unable to render document.')}, status=400
        )
    response = FileResponse(BytesIO(pdf), filename='document.pdf')
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def area_image_context(domain, area_name, image_id, error=None):
    """The context of the image fields of an area in the editor"""
    return {
        'domain': domain,
        'area': area_name,
        'image_id': image_id,
        'thumbnail_url': get_thumbnail_url(image_id) if image_id else '',
        'error': error,
    }


@require_permission(HqPermissions.edit_document_templates)
@toggles.DOCUMENT_TEMPLATES.required_decorator()
@require_POST
def upload_area_image(request, domain, area):
    """HTMX partial for the editor: stores the uploaded image and returns the image fields of the area

    The form is posted with the request, so the image the area has now is kept
    when the upload is rejected.
    """
    if area not in get_area_names():
        raise Http404()
    image_id = request.POST.get(f'{AREA_FIELD_PREFIX}{area}_image', '')
    error = None
    try:
        image_id = save_image(domain, request.FILES.get('image_file'), request.couch_user.username)
    except ImageError as exception:
        error = str(exception)
    context = area_image_context(domain, area, image_id, error)
    return HttpResponse(render_to_string('document_templates/partials/area_image.html', context))
