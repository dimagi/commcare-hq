import json
import re

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, validate_slug
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.app_manager.helpers.validators import load_case_reserved_words
from corehq.toggles import REGEX_FIELD_VALIDATION

from .models import (
    CustomDataFieldsDefinition,
    Field,
    validate_reserved_words,
)


class CustomDataFieldsForm(forms.Form):
    """
    The main form for editing a custom data definition
    """
    data_fields = forms.CharField(widget=forms.HiddenInput)
    purge_existing = forms.BooleanField(widget=forms.HiddenInput, required=False, initial=False)

    def verify_no_duplicates(self, data_fields):
        errors = set()
        slugs = [field['slug'].lower()
                 for field in data_fields if 'slug' in field]
        for slug in slugs:
            if slugs.count(slug) > 1:
                errors.add(_("Key '{}' was duplicated, key names must be "
                             "unique.").format(slug))
        return errors

    def verify_no_reserved_words(self, data_fields):
        case_reserved_words = load_case_reserved_words()
        errors = set()
        slugs = [field['slug'].lower()
                 for field in data_fields if 'slug' in field]
        for slug in slugs:
            if slug in case_reserved_words:
                errors.add(_("Key '{}' is a reserved word in Commcare.").format(slug))
        return errors

    def clean_data_fields(self):
        raw_data_fields = json.loads(self.cleaned_data['data_fields'])
        errors = set()
        data_fields = []
        for raw_data_field in raw_data_fields:
            data_field_form = CustomDataFieldForm(raw_data_field)
            data_field_form.is_valid()
            data_fields.append(data_field_form.cleaned_data)
            if data_field_form.errors:
                errors.update([error[0]
                               for error in data_field_form.errors.values()])

        errors.update(self.verify_no_duplicates(data_fields))
        errors.update(self.verify_no_reserved_words(data_fields))

        if errors:
            raise ValidationError('<br/>'.join(sorted(errors)))

        return data_fields


class XmlSlugField(forms.SlugField):
    default_validators = [
        validate_slug,
        validate_reserved_words,
        RegexValidator(r'\D', ''),  # disallow property names that are just numbers, which breaks
    ]


class CustomDataFieldForm(forms.Form):
    """
    Sub-form for editing an individual field's definition.
    """
    label = forms.CharField(
        required=True,
        error_messages={'required': ugettext_lazy('A label is required for each field.')}
    )
    slug = XmlSlugField(
        required=True,
        error_messages={
            'required': ugettext_lazy('A property name is required for each field.'),
            'invalid': ugettext_lazy('Properties must start with a letter and '
                         'consist only of letters, numbers, underscores or hyphens.'),
        }
    )
    is_required = forms.BooleanField(required=False)
    choices = forms.CharField(widget=forms.HiddenInput, required=False)
    regex = forms.CharField(required=False)
    regex_msg = forms.CharField(required=False)

    def __init__(self, raw, *args, **kwargs):
        # Pull the raw_choices out here, because Django incorrectly
        # serializes the list and you can't get it
        self._raw_choices = [_f for _f in raw.get('choices', []) if _f]
        super(CustomDataFieldForm, self).__init__(raw, *args, **kwargs)

    def clean_choices(self):
        return self._raw_choices

    def clean_regex(self):
        regex = self.cleaned_data.get('regex')
        if regex:
            try:
                re.compile(regex)
            except Exception:
                raise ValidationError(_("Not a valid regular expression"))
        return regex


class CustomDataFieldsProfileForm(forms.Form):
    """
    Sub-form for editing a single profile
    """
    name = forms.CharField(
        required=True,
        error_messages={'required': ugettext_lazy('All fields are required')}
    )
    fields = forms.CharField(
        required=True,
        error_messages={'required': ugettext_lazy('At least one field is required')}
    )

    def clean_fields(self):
        fields = self.data.get('fields')
        if fields:
            return json.dumps(fields)
        return fields


class CustomDataModelMixin(object):
    """
    Provides the interface for editing the ``CustomDataFieldsDefinition``
    for each entity type.
    Each entity type must provide a subclass of this mixin.
    """
    urlname = None
    template_name = "custom_data_fields/custom_data_fields.html"
    field_type = None
    show_profiles = False
    show_purge_existing = False
    entity_string = None  # User, Group, Location, Product...

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(CustomDataModelMixin, self).dispatch(request, *args, **kwargs)

    @classmethod
    def get_validator(cls, domain):
        data_model = CustomDataFieldsDefinition.get_or_create(domain, cls.field_type)
        return data_model.get_validator()

    @classmethod
    def page_name(cls):
        return _("Edit {} Fields").format(str(cls.entity_string))

    def get_definition(self):
        return CustomDataFieldsDefinition.get_or_create(self.domain, self.field_type)

    def save_custom_fields(self):
        definition = self.get_definition()
        definition.field_type = self.field_type
        definition.domain = self.domain
        definition.set_fields([
            self.get_field(field)
            for field in self.form.cleaned_data['data_fields']
        ])
        definition.save()

    def get_field(self, field):
        if REGEX_FIELD_VALIDATION.enabled(self.domain) and field.get('regex'):
            choices = []
            regex = field.get('regex')
            regex_msg = field.get('regex_msg')
        else:
            choices = field.get('choices')
            regex = None
            regex_msg = None
        return Field(
            slug=field.get('slug'),
            is_required=field.get('is_required'),
            label=field.get('label'),
            choices=choices,
            regex=regex,
            regex_msg=regex_msg,
        )

    @property
    def page_context(self):
        return {
            "custom_fields": json.loads(self.form.data['data_fields']),
            "custom_fields_form": self.form,
            "show_profiles": self.show_profiles,
            "show_purge_existing": self.show_purge_existing,
        }

    @property
    @memoized
    def form(self):
        if self.request.method == "POST":
            return CustomDataFieldsForm(self.request.POST)
        else:
            definition = self.get_definition()
            serialized = json.dumps([
                {
                    'slug': field.slug,
                    'is_required': field.is_required,
                    'label': field.label,
                    'choices': field.choices,
                    'regex': field.regex,
                    'regex_msg': field.regex_msg,
                } for field in definition.get_fields()
            ])
            return CustomDataFieldsForm({'data_fields': serialized})

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.save_custom_fields()
            if self.show_purge_existing and self.form.cleaned_data['purge_existing']:
                self.update_existing_models()
            msg = _("{} fields saved successfully").format(
                str(self.entity_string)
            )
            messages.success(request, msg)
            return redirect(self.urlname, self.domain)
        else:
            return self.get(request, *args, **kwargs)

    def update_existing_models(self):
        """
        Subclasses with show_purge_exiting set to True should override this to update existing models
        """
        raise NotImplementedError()
