import json

from collections import OrderedDict

from django import forms
from django.core.validators import RegexValidator
from django.forms.widgets import Select
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.html import escape
from corehq.apps.accounting.utils import domain_has_privilege

from crispy_forms.layout import HTML, Div, Field, Fieldset, Layout
from memoized import memoized

from corehq.apps.hqwebapp.crispy import HQFormHelper, HQModalFormHelper
from corehq import privileges

from .models import (
    CUSTOM_DATA_FIELD_PREFIX,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    PROFILE_SLUG,
    is_system_key,
)


def with_prefix(string, prefix):
    """
    Prefix single string with the defined
    custom data prefix (such as data-field-whatevs).
    """
    return "{}-{}".format(prefix, string)


def without_prefix(string, prefix):
    prefix_len = len(prefix) + 1
    return string[prefix_len:] if string.startswith(prefix) else string


def add_prefix(field_dict, prefix):
    """
    Prefix all keys in the dict.
    """
    return {
        with_prefix(k, prefix): v
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
                 prefix=None, required_only=False, ko_model=None, request_user=None):
        self.field_view = field_view
        self.domain = domain
        self.existing_custom_data = existing_custom_data
        self.required_only = required_only
        self.ko_model = ko_model
        self.prefix = prefix if prefix is not None else CUSTOM_DATA_FIELD_PREFIX
        self.request_user = request_user
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
        return dict(system_data, **cleaned_data)    # cleaned_data may overwrite existing system data

    def _make_field(self, field):
        safe_label = escape(field.label)
        is_required_field = self.field_view.is_field_required(field)
        if field.regex:
            validator = RegexValidator(field.regex, field.regex_msg)
            return forms.CharField(label=safe_label, required=is_required_field,
                                   validators=[validator])
        elif field.choices:
            # If form uses knockout, knockout must have control over the select2.
            # Otherwise, use .hqwebapp-select2 and hqwebapp/js/bootstrap3/widgets to make the select2.
            attrs = {
                'data-placeholder': _('Select one'),
                'data-allow-clear': 'true',
            }
            if self.ko_model:
                placeholder_choices = []
            else:
                attrs.update({'class': 'hqwebapp-select2'})
                # When options are provided only in HTML, placeholder must also have an HTML element
                placeholder_choices = [('', _('Select one'))]

            return forms.ChoiceField(
                label=safe_label,
                required=is_required_field,
                choices=placeholder_choices + [(c, c) for c in field.choices],
                widget=forms.Select(attrs=attrs)
            )
        else:
            return forms.CharField(label=safe_label, required=is_required_field)

    def make_fieldsets(self, form_fields, is_post, field_name_includes_prefix=False):
        if self.ko_model:
            field_names = []
            for field_name, field in form_fields.items():
                data_bind_field_name = (
                    without_prefix(field_name, self.prefix) if field_name_includes_prefix else field_name)
                data_binds = [
                    f"value: {self.ko_model}['{data_bind_field_name}'].value",
                    f"disable: {self.ko_model}['{data_bind_field_name}'].disable",
                ]
                if hasattr(field, 'choices') or without_prefix(field_name, self.prefix) == PROFILE_SLUG:
                    data_binds.append("select2: " + json.dumps([
                        {"id": id, "text": text} for id, text in field.widget.choices
                    ]))
                field_names.append(Field(
                    field_name,
                    data_bind=", ".join(data_binds)
                ))
        else:
            field_names = list(form_fields)

        form_fieldsets = []
        if field_names:
            form_fieldsets.append(Fieldset(
                _("Additional Information"),
                *field_names,
                css_class="custom-data-fieldset"
            ))
        if not is_post:
            form_fieldsets.append(self.uncategorized_form)
        return form_fieldsets

    @property
    @memoized
    def fields(self):
        field_filter_config = CustomDataFieldsDefinition.FieldFilterConfig(
            required_only=self.required_only,
            is_required_check_func=self.field_view.is_field_required
        )
        return list(self.model.get_fields(field_filter_config=field_filter_config))

    def init_form(self, post_dict=None):
        form_fields = OrderedDict()

        from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
        has_profile_privilege_and_is_user_fields_view = (
            domain_has_privilege(self.domain, privileges.APP_USER_PROFILES)
            and issubclass(self.field_view, UserFieldsView)
        )
        if has_profile_privilege_and_is_user_fields_view:
            original_profile_id = None
            if self.existing_custom_data:
                original_profile_id = self.existing_custom_data.get(PROFILE_SLUG, None)

            profiles, can_edit_original_profile = self.field_view.get_displayable_profiles_and_edit_permission(
                original_profile_id, self.domain, self.request_user
            )

            def profile_selection_required():
                user_type = self.field_view.user_type
                profile_required_list_user_types = self.model.profile_required_for_user_type or []

                return user_type in profile_required_list_user_types

            def validate_profile_slug(value):
                from django.core.exceptions import ValidationError
                if value not in [p.id for p in profiles]:
                    raise ValidationError(
                        _('Invalid profile selected. Please select a valid profile.'),
                    )

            if profiles:
                attrs = {
                    'data-placeholder': _('Select a profile'),
                    'data-allow-clear': 'true',
                }
                if not self.ko_model:
                    attrs.update({'class': 'hqwebapp-select2'})
                form_fields[PROFILE_SLUG] = forms.IntegerField(
                    label=_('Profile'),
                    required=profile_selection_required(),
                    widget=Select(choices=[
                        (p.id, p.name)
                        for p in profiles
                    ], attrs=attrs),
                    validators=[validate_profile_slug],
                )
        for field in self.fields:
            form_fields[field.slug] = self._make_field(field)

        CustomDataForm = type('CustomDataForm', (forms.Form,), form_fields.copy())
        if self.ko_model:
            CustomDataForm.helper = HQModalFormHelper()
        else:
            CustomDataForm.helper = HQFormHelper()
        CustomDataForm.helper.form_tag = False

        form_fieldsets = self.make_fieldsets(form_fields, post_dict is not None)

        CustomDataForm.helper.layout = Layout(
            *form_fieldsets
        )

        CustomDataForm._has_uncategorized = bool(self.uncategorized_form) and post_dict is None

        if post_dict:
            form_data = post_dict.copy()   # make mutable
        elif self.existing_custom_data is not None:
            form_data = add_prefix(self.existing_custom_data, self.prefix)
        else:
            form_data = None

        # Add profile fields so that form validation passes
        if form_data and has_profile_privilege_and_is_user_fields_view:

            # When a field is disabled via knockout, it is not included in POST so this
            # adds it back
            if (post_dict and (with_prefix(PROFILE_SLUG, self.prefix)) not in post_dict
                    and not can_edit_original_profile):
                form_data.update({with_prefix(PROFILE_SLUG, self.prefix): original_profile_id})
            try:
                profile_fields = CustomDataFieldsProfile.objects.get(
                    id=int(form_data.get(with_prefix(PROFILE_SLUG, self.prefix))),
                    definition__field_type=self.field_view.field_type,
                    definition__domain=self.domain,
                ).fields
            except (ValueError, TypeError, CustomDataFieldsProfile.DoesNotExist):
                profile_fields = {}
            form_data.update(add_prefix(profile_fields, self.prefix))

        self.form = CustomDataForm(form_data, prefix=self.prefix)
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
