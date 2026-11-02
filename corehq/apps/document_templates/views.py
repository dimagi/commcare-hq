from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext, gettext_lazy

from corehq import toggles
from corehq.apps.document_templates.models import Template, Variable
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


VARIABLE_FIELD_PREFIX = 'var_'


def get_variable_names():
    # TODO: replace with the real list of variable names
    return ['header', 'address', 'body', 'footer']

class TemplateForm(forms.ModelForm):
    class Meta:
        model = Template
        fields = ['name', 'slug']

    def __init__(self, *args, domain, variable_names, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.domain = domain
        self.variable_names = variable_names
        saved_variables = self.instance.variables or {}
        for variable_name in variable_names:
            variable = saved_variables.get(variable_name)
            self.fields[self._field_name(variable_name)] = forms.CharField(
                label=variable_name,
                required=False,
                initial=variable.value if variable else '',
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
    def _field_name(variable_name):
        return f'{VARIABLE_FIELD_PREFIX}{variable_name}'

    def variable_fields(self):
        return [self[self._field_name(name)] for name in self.variable_names]

    def get_variables(self):
        return {
            variable_name: Variable(value=self.cleaned_data[self._field_name(variable_name)])
            for variable_name in self.variable_names
        }

    def save(self, commit=True):
        self.instance.variables = self.get_variables()
        return super().save(commit=commit)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class NewDocumentTemplateView(BaseMessagingSectionView):
    urlname = 'new_document_template'
    page_title = gettext_lazy('New Template')
    template_name = 'document_templates/template_form.html'
    instance = None

    @cached_property
    def form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return TemplateForm(
            data,
            domain=self.domain,
            variable_names=get_variable_names(),
            instance=self.instance,
        )

    @property
    def page_context(self):
        return {'form': self.form}

    def save_template(self):
        return self.form.save()

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
        return get_object_or_404(Template, domain=self.domain, pk=self.kwargs['template_id'], deleted=False)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.document_template.pk])

    @property
    def instance(self):
        return self.document_template


@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class DeleteDocumentTemplateView(BaseMessagingSectionView):
    urlname = 'delete_document_template'
    http_method_names = ['post']

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['template_id']])

    def post(self, request, *args, **kwargs):
        template = get_object_or_404(Template, domain=self.domain, pk=kwargs['template_id'], deleted=False)
        template.deleted = True
        template.save(update_fields=['deleted'])
        return HttpResponseRedirect(
            reverse(DocumentTemplatesView.urlname, args=[self.domain])
        )
