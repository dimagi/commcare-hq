import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.utils.translation import ugettext as _, ugettext_noop
from django import forms

from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from dimagi.utils.decorators.memoized import memoized

from .models import CustomDataFieldsDefinition, CustomDataField, CUSTOM_DATA_FIELD_PREFIX


class CustomDataFieldsForm(forms.Form):
    data_fields = forms.CharField(widget=forms.HiddenInput)

    def clean_data_fields(self):
        raw_data_fields = json.loads(self.cleaned_data['data_fields'])
        errors = set()
        data_fields = []
        for raw_data_field in raw_data_fields:
            data_field_form = CustomDataFieldForm(raw_data_field)
            data_field_form.is_valid()
            data_fields.append(data_field_form.cleaned_data)
            if data_field_form.errors:
                errors.update([error[0] for error in data_field_form.errors.values()])
        if errors:
            raise ValidationError('<br/>'.join(errors))
        return data_fields


class CustomDataFieldForm(forms.Form):
    label = forms.CharField(
        required=True,
        error_messages={'required': _('All fields are required')}
    )
    slug = forms.SlugField(
        required=True,
        error_messages={
            'required': _('All fields are required'),
            'invalid': _('Key fields must consist only of letters, numbers, underscores or hyphens.')
        }
    )
    is_required = forms.BooleanField(required=False)

    def clean_label(self):
        return self.cleaned_data['label']

    def clean_slug(self):
        return self.cleaned_data['slug']


class CustomDataFieldsMixin(object):
    urlname = None
    template_name = "custom_data_fields/custom_data_fields.html"
    page_name = ugettext_noop("Edit Custom Fields")
    doc_type = None
    field_type = None
    form_label = None

    def get_definition(self):
        return CustomDataFieldsDefinition.by_domain(self.domain, self.field_type)

    def get_custom_fields(self):
        definition = self.get_definition()
        if definition:
            return definition.fields
        else:
            return []

    def save_custom_fields(self):
        definition = self.get_definition() or CustomDataFieldsDefinition()
        definition.doc_type = self.field_type
        definition.domain = self.domain
        definition.fields = [
            self.get_field(field)
            for field in self.form.cleaned_data['data_fields']
        ]
        definition.save()

    def get_field(self, field):
        return CustomDataField(
            slug=field.get('slug'),
            is_required=field.get('is_required'),
            label=field.get('label'),
        )

    @property
    def page_context(self):
        return {
            "custom_fields": json.loads(self.form.data['data_fields']),
            "custom_fields_form": self.form,
        }

    @property
    @memoized
    def form(self):
        if self.request.method == "POST":
            return CustomDataFieldsForm(self.request.POST)
        else:
            serialized = json.dumps([field.to_json() for field in self.get_custom_fields()])
            return CustomDataFieldsForm({'data_fields': serialized})

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.save_custom_fields()
            return self.get(request, success=True, *args, **kwargs)
        else:
            return self.get(request, *args, **kwargs)


class CustomDataEditor(object):
    def __init__(self, field_type, domain, user):
        self.field_type = field_type
        self.domain = domain
        self.user = user
        self.form = None

    @property
    @memoized
    def model(self):
        definition = CustomDataFieldsDefinition.by_domain(
            self.domain,
            self.field_type,
        )
        return definition or CustomDataFieldsDefinition()

    @property
    def template_fields(self):
        return [
            {
                'slug': field.html_slug,
                'label': field.label,
                'value': self.user.user_data.get(field.slug, ''),
            } for field in self.model.fields
        ]
        pass

    def save_to_user(self):
        if self.form:
            self.user.user_data = self.form.cleaned_data

    def init_form(self, post_dict):
        def _make_field(field):
            return forms.CharField(required=field.is_required)

        fields = {
            field.slug: _make_field(field) for field in self.model.fields
        }
        CustomDataForm = type('CustomDataForm', (forms.Form,), fields)

        fields = {
            key[len(CUSTOM_DATA_FIELD_PREFIX):]: value
            for key, value in post_dict.items()
            if key.startswith(CUSTOM_DATA_FIELD_PREFIX)
        }

        self.form = CustomDataForm(fields)
        return self.form
