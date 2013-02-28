from django import forms
from django.conf import settings
from django.forms.util import ErrorList
from corehq.apps.crud.models import BaseAdminCRUDForm
from corehq.apps.indicators.models import FormDataAliasIndicatorDefinition, FormLabelIndicatorDefinition
from dimagi.utils.decorators.memoized import memoized


class BaseIndicatorDefinitionForm(BaseAdminCRUDForm):
    slug = forms.SlugField(label="Slug")
    namespace = forms.CharField(label="Namespace", widget=forms.Select(choices=[]))
    version = forms.IntegerField(label="Version No.")

    namespace_map = "INDICATOR_NAMESPACES"

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, doc_id=None, domain=None):
        super(BaseIndicatorDefinitionForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
                                                          label_suffix, empty_permitted, doc_id)
        self.domain = domain
        available_namespaces = getattr(settings, self.namespace_map, {})
        self.fields['namespace'].widget = forms.Select(choices=available_namespaces.get(self.domain, ()))

    @property
    @memoized
    def crud_manager(self):
        crud_manager = super(BaseIndicatorDefinitionForm, self).crud_manager
        crud_manager.domain = self.domain
        return crud_manager


class FormLabelIndicatorDefinitionForm(BaseIndicatorDefinitionForm):
    xmlns = forms.CharField(label="XMLNS")

    def clean_xmlns(self):
        if 'xmlns' in self.cleaned_data:
            xmlns = self.cleaned_data['xmlns']
            return xmlns.strip()

    doc_class = FormLabelIndicatorDefinition


class FormDataAliasIndicatorDefinitionForm(FormLabelIndicatorDefinitionForm):
    question_id = forms.CharField(label="Question ID")

    doc_class = FormDataAliasIndicatorDefinition
