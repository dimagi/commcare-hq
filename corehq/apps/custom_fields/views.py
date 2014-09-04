import json

from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_noop
from django import forms

from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from dimagi.utils.decorators.memoized import memoized

from .models import CustomFieldsDefinition, CustomField


class CustomDataFieldsForm(forms.Form):
    data_fields = forms.CharField(widget=forms.HiddenInput)

    def clean_data_fields(self):
        raw_data_fields = json.loads(self.cleaned_data['data_fields'])
        errors = []
        data_fields = []
        for raw_data_field in raw_data_fields:
            data_field_form = CustomDataFieldForm(raw_data_field)
            data_field_form.is_valid()
            data_fields.append(data_field_form.cleaned_data)
            errors.append(data_field_form.errors)
        return data_fields


class CustomDataFieldForm(forms.Form):
    label = forms.CharField()
    slug = forms.CharField()
    is_required = forms.BooleanField()


class CustomFieldsMixin(object):
    urlname = None
    template_name = "custom_fields/custom_fields.html"
    # form_class = CustomFieldsForm
    page_name = ugettext_noop("Edit Custom Fields")
    doc_type = None

    def get_definition(self):
        return CustomFieldsDefinition.by_domain(self.domain, 'UserFields')

    def get_custom_fields(self):
        definition = self.get_definition()
        if definition:
            return definition.fields
        else:
            return [
                {"slug": "dob", "label": "not found", "is_required": True},
                {"slug": "gender", "label": "Gender", "is_required": False},
            ]

    def save_custom_fields(self):
        definition = self.get_definition() or CustomFieldsDefinition()
        definition.doc_type = 'UserFields'
        definition.domain = self.domain
        definition.fields = [
            self.get_field(field)
            for field in self.form.cleaned_data['data_fields']
        ]
        definition.save()

    def get_field(self, field):
        return CustomField(
            slug=field.get('slug'),
            is_required=field.get('is_required'),
            label=field.get('label'),
        )

    @property
    def page_context(self):
        return {
            "custom_fields": self.get_custom_fields(),
        }

    @property
    @memoized
    def form(self):
        return CustomDataFieldsForm(self.request.POST)

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.save_custom_fields()
        return self.get(request, success=True, *args, **kwargs)
