from collections import OrderedDict

from django import forms
from django.core.validators import RegexValidator
from django.urls import reverse
from django.utils.translation import ugettext as _

from crispy_forms.layout import HTML, Div, Field, Fieldset, Layout
from memoized import memoized

from corehq.apps.hqwebapp.crispy import HQFormHelper, HQModalFormHelper

from .models import (
    CUSTOM_DATA_FIELD_PREFIX,
    CustomDataFieldsDefinition,
    is_system_key,
)


def add_prefix(field_dict, prefix):
    """
    Prefix all keys in the dict with the defined
    custom data prefix (such as data-field-whatevs).
    """
    return {
        "{}-{}".format(prefix, k): v
        for k, v in field_dict.items()
    }


def get_prefixed(field_dict, prefix):
    """
    The inverse of add_prefix.
    Returns all prefixed elements of a dict with the prefices stripped.
    """
    prefix_len = len(prefix) + 1
    return {
        k[prefix_len:]: v
        for k, v in field_dict.items()
        if k.startswith(prefix)
    }


class CustomDataEditor(object):
    """
    Tool to edit the data for a particular entity, like for an individual user.
    """

    def __init__(self, field_view, domain, existing_custom_data=None, post_dict=None,
                 prefix=None, required_only=False, ko_model=None):
        self.field_view = field_view
        self.domain = domain
        self.existing_custom_data = existing_custom_data
        self.required_only = required_only
        self.ko_model = ko_model
        self.prefix = prefix if prefix is not None else CUSTOM_DATA_FIELD_PREFIX
        self.form = self.init_form(post_dict)

    @property
    @memoized
    def model(self):
        return CustomDataFieldsDefinition.get_or_create(
            self.domain,
            self.field_view.field_type,
        )

    def is_valid(self):
        return not self.errors

    @property
    def errors(self):
        # form.errors calls full_clean if needed and is idempotent
        return self.form.errors

    def get_data_to_save(self):
        if not self.is_valid():
            raise AssertionError("Form is invalid, you can't call this yet.")
        cleaned_data = self.form.cleaned_data
        system_data = {
            k: v for k, v in self.existing_custom_data.items()
            if is_system_key(k)
        } if self.existing_custom_data else {}
        # reset form to clear uncategorized data
        self.existing_custom_data = None
        self.form = self.init_form(add_prefix(cleaned_data, self.prefix))
        self.form.is_valid()
        return dict(cleaned_data, **system_data)

    def _make_field(self, field):
        if field.regex:
            validator = RegexValidator(field.regex, field.regex_msg)
            return forms.CharField(label=field.label, required=field.is_required,
                                   validators=[validator])
        elif field.choices:
            return forms.ChoiceField(
                label=field.label,
                required=field.is_required,
                choices=[('', _('Select one'))] + [(c, c) for c in field.choices],
                widget=forms.Select(attrs={'class': 'hqwebapp-select2'}),
            )
            return choice_field
        else:
            return forms.CharField(label=field.label, required=field.is_required)

    @property
    @memoized
    def fields(self):
        return list(self.model.get_fields(required_only=self.required_only))

    def init_form(self, post_dict=None):
        fields = OrderedDict()
        for field in self.fields:
            fields[field.slug] = self._make_field(field)

        if self.ko_model:
            field_names = [
                Field(
                    field_name,
                    data_bind="value: {}.{}".format(self.ko_model, field_name),
                )
                for field_name, field in fields.items()
            ]
        else:
            field_names = list(fields)

        CustomDataForm = type('CustomDataForm', (forms.Form,), fields)
        if self.ko_model:
            CustomDataForm.helper = HQModalFormHelper()
        else:
            CustomDataForm.helper = HQFormHelper()
        CustomDataForm.helper.form_tag = False

        additional_fields = []
        if field_names:
            additional_fields.append(Fieldset(_("Additional Information"), *field_names))
        if post_dict is None:
            additional_fields.append(self.uncategorized_form)
        CustomDataForm.helper.layout = Layout(
            *additional_fields
        )

        CustomDataForm._has_uncategorized = bool(self.uncategorized_form) and post_dict is None

        if post_dict:
            fields = post_dict
        elif self.existing_custom_data is not None:
            fields = add_prefix(self.existing_custom_data, self.prefix)
        else:
            fields = None

        self.form = CustomDataForm(fields, prefix=self.prefix)
        return self.form

    @property
    @memoized
    def uncategorized_form(self):

        def FakeInput(val):
            return HTML('<p class="form-control-static">{}</p>'
                        .format(val))

        def Label(val):
            return HTML('<label class="control-label col-sm-3 col-md-2">{}</label>'.format(val))

        def _make_field_div(slug, val):
            return Div(
                Label(slug),
                Div(
                    FakeInput(val),
                    css_class="controls col-sm-9 col-md-8 col-lg-6",
                ),
                css_class="form-group",
            )

        fields = [f.slug for f in self.model.get_fields()]
        help_div = [
            _make_field_div(slug, val)
            for slug, val in self.existing_custom_data.items()
            if (slug not in fields and not is_system_key(slug))
        ] if self.existing_custom_data is not None else []

        msg = """
        <strong>Warning!</strong>
        This data is not part of the specified {} fields and will be deleted when you save.
        You can add the fields back <a href="{}">here</a> to prevent this deletion.
        """.format(self.field_view.entity_string.lower(), reverse(
            self.field_view.urlname, args=[self.domain]
        ))

        return Fieldset(
            _("Unrecognized Information"),
            Div(
                HTML(msg),
                css_class="alert alert-warning",
                css_id="js-unrecognized-data",
            ),
            *help_div
        ) if len(help_div) else HTML('')
