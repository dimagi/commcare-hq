import json
import re

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, validate_slug
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.safestring import mark_safe
from django.utils.html import format_html_join
from corehq.apps.accounting.utils import domain_has_privilege
from corehq import privileges

from memoized import memoized
from corehq.apps.callcenter.tasks import bulk_sync_usercases_if_applicable

from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.app_manager.helpers.validators import load_case_reserved_words

from .models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
    validate_reserved_words,
)
from .tasks import refresh_es_for_profile_users


class CustomDataFieldsForm(forms.Form):
    """
    The main form for editing a custom data definition
    """
    data_fields = forms.CharField(widget=forms.HiddenInput)
    purge_existing = forms.BooleanField(widget=forms.HiddenInput, required=False, initial=False)
    profiles = forms.CharField(widget=forms.HiddenInput)

    @classmethod
    def verify_no_duplicates(cls, data_fields):
        errors = set()
        slugs = [field['slug'].lower()
                 for field in data_fields if 'slug' in field]
        for slug in slugs:
            if slugs.count(slug) > 1:
                errors.add(_("Key '{}' was duplicated, key names must be "
                             "unique.").format(slug))
        return errors

    @classmethod
    def verify_no_reserved_words(cls, data_fields):
        case_reserved_words = load_case_reserved_words()
        errors = set()
        slugs = [field['slug'].lower()
                 for field in data_fields if 'slug' in field]
        for slug in slugs:
            if slug in case_reserved_words:
                errors.add(_("Key '{}' is a reserved word in Commcare.").format(slug))
        return errors

    @classmethod
    def verify_no_duplicate_profiles(cls, profiles):
        errors = set()
        names = [profile.get('name') for profile in profiles]
        for name in names:
            if names.count(name) > 1:
                errors.add(_("Profile name '{}' appears more than once. Profile names must be "
                             "unique.").format(name))
        return errors

    @classmethod
    def verify_no_profiles_missing_fields(cls, data_fields, profiles):
        errors = set()
        slugs = {field['slug']
                 for field in data_fields if 'slug' in field}
        for profile in profiles:
            for field in json.loads(profile.get('fields', "{}")).keys():
                if field not in slugs:
                    errors.add(_("Profile '{}' contains '{}' which is not a known field.").format(
                        profile['name'], field
                    ))
        return errors

    @classmethod
    def verify_no_empty_profile_fields(cls, data_fields, profiles):
        errors = set()

        required_field_names = {field['slug'] for field in data_fields if field['is_required']}
        for profile in profiles:
            profile_fields = json.loads(profile.get('fields', '{}'))
            for slug, value in profile_fields.items():
                if slug in required_field_names and not value:
                    errors.add(_("Profile '{}' does not assign a value for required field '{}'").format(
                        profile['name'], slug
                    ))
        return errors

    @classmethod
    def verify_profiles_validate(cls, data_fields, profiles):
        errors = set()
        fields_by_slug = {
            field['slug']: Field(
                slug=field.get('slug'),
                is_required=field.get('is_required'),
                label=field.get('label'),
                choices=field.get('choices'),
                regex=field.get('regex'),
                regex_msg=field.get('regex_msg'),
            ) for field in data_fields if field.get('slug')
        }
        for profile in profiles:
            for key, value in json.loads(profile.get('fields', '{}')).items():
                field = fields_by_slug.get(key)
                if field:
                    # Only one of these two will run, depending on field's data.
                    # The other one will return early.
                    errors.add(field.validate_choices(value))
                    errors.add(field.validate_regex(value))
        return {e for e in errors if e}

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

    def clean_profiles(self):
        raw_profiles = json.loads(self.cleaned_data['profiles'])

        errors = set()
        profiles = []
        for raw_profile in raw_profiles:
            profile_form = CustomDataFieldsProfileForm(raw_profile)
            profile_form.is_valid()
            profiles.append(profile_form.cleaned_data)
            if profile_form.errors:
                errors.update([error[0] for error in profile_form.errors.values()])

        if errors:
            raise ValidationError('<br/>'.join(sorted(errors)))

        return profiles

    def clean(self):
        cleaned_data = super().clean()
        data_fields = self.cleaned_data.get('data_fields')
        profiles = self.cleaned_data.get('profiles', [])

        errors = set()
        errors.update(self.verify_no_duplicate_profiles(profiles))
        if data_fields is not None:
            errors.update(self.verify_no_profiles_missing_fields(data_fields, profiles))
            errors.update(self.verify_profiles_validate(data_fields, profiles))
            errors.update(self.verify_no_empty_profile_fields(data_fields, profiles))

        if errors:
            separator = mark_safe('<br/>')  # nosec: no user input
            error_html = format_html_join(separator, '{}', ((error,) for error in sorted(errors)))
            raise ValidationError(error_html)

        return cleaned_data


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
        error_messages={'required': gettext_lazy('A label is required for each field.')}
    )
    slug = XmlSlugField(
        required=True,
        error_messages={
            'required': gettext_lazy('A property name is required for each field.'),
            'invalid': gettext_lazy('Properties must start with a letter and '
                         'consist only of letters, numbers, underscores or hyphens.'),
        }
    )
    is_required = forms.BooleanField(required=False)
    choices = forms.CharField(widget=forms.HiddenInput, required=False)
    regex = forms.CharField(required=False)
    regex_msg = forms.CharField(required=False)
    upstream_id = forms.CharField(required=False, empty_value=None)

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
    id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )
    name = forms.CharField(
        required=True,
        error_messages={'required': gettext_lazy('A name is required for each profile.')}
    )
    fields = forms.CharField(
        required=True,
        error_messages={'required': gettext_lazy('At least one field is required for each profile.')}
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
    _show_profiles = False
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

    @property
    def show_profiles(self):
        return self._show_profiles and domain_has_privilege(self.domain, privileges.APP_USER_PROFILES)

    @memoized
    def get_definition(self):
        return CustomDataFieldsDefinition.get_or_create(self.domain, self.field_type)

    @memoized
    def get_profiles(self):
        return self.get_definition().get_profiles()

    @classmethod
    def validate_incoming_fields(cls, existing_fields, new_fields, can_edit_linked_data=False):
        existing_synced_fields = {field.upstream_id: field for field in existing_fields if field.upstream_id}

        errors = []
        for new_field in new_fields:
            if not new_field.upstream_id:
                continue  # Only deal with synced data

            matching_field = existing_synced_fields.pop(new_field.upstream_id, None)

            # check that any upstream_ids were already present. If not, the submitter is trying to
            # create new synced data, which is not allowed
            if not matching_field:
                errors.append(
                    _("Could not update '{}'. Synced data cannot be created this way").format(new_field.slug))
            elif not can_edit_linked_data:
                # Ensure no changes were done to this field
                if new_field.to_dict() != matching_field.to_dict():
                    errors.append(
                        _("Could not update '{}'. You do not have the appropriate role").format(new_field.slug))

        # Any remaining items in the existing_synced_fields will be deleted.
        # Ensure the user has permission to do this
        if existing_synced_fields and not can_edit_linked_data:
            errors.append(_("Unable to remove synced fields. You do not have the appropriate role"))

        return errors

    def save_custom_fields(self):
        definition = self.get_definition()

        incoming_fields = [self.get_field(field) for field in self.form.cleaned_data['data_fields']]

        field_errors = self.validate_incoming_fields(
            definition.get_fields(), incoming_fields, can_edit_linked_data=self.can_edit_linked_data())

        if field_errors:
            return field_errors

        definition.field_type = self.field_type
        definition.domain = self.domain
        definition.set_fields(incoming_fields)
        definition.save()

        return []  # no errors

    def save_profiles(self):
        if not self.show_profiles:
            return []

        definition = self.get_definition()
        seen = set()
        for profile in self.form.cleaned_data['profiles']:
            (obj, created) = CustomDataFieldsProfile.objects.update_or_create(
                id=profile['id'], defaults={
                    "definition": definition,
                    "name": profile['name'],
                    "fields": json.loads(profile['fields']),
                }
            )
            if not created and obj.has_users_assigned:
                refresh_es_for_profile_users.delay(self.domain, obj.id)
                bulk_sync_usercases_if_applicable(obj.definition.domain, obj.user_ids_assigned())
            seen.add(obj.id)

        errors = []
        for profile in self.get_profiles():
            if profile.id not in seen:
                if profile.has_users_assigned:
                    errors.append(_("Could not delete profile '{}' because it has users "
                                    "assigned.").format(profile.name))
                else:
                    profile.delete()

        return errors

    def get_field(self, field):
        if domain_has_privilege(self.domain, privileges.REGEX_FIELD_VALIDATION) and field.get('regex'):
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
            upstream_id=field.get('upstream_id')
        )

    @property
    def page_context(self):
        context = {
            "custom_fields": json.loads(self.form.data['data_fields']),
            "custom_fields_form": self.form,
            "disable_save": self.request.method == "GET" or self.form.is_valid(),
            "show_purge_existing": self.show_purge_existing,
            "profiles_active": self.show_profiles and self.request.POST.get("profiles_active", "false") == "true",
            "can_view_regex_field_validation": (
                domain_has_privilege(self.domain, privileges.REGEX_FIELD_VALIDATION)
                or self.request.user.is_superuser
            ),
            "is_managed_by_upstream_domain": self.is_managed_by_upstream_domain(),
            "can_edit_linked_data": self.can_edit_linked_data(),
        }
        if self.show_profiles:
            profiles = json.loads(self.form.data['profiles'])
            context.update({
                "show_profiles": True,
                "custom_fields_profiles": sorted(profiles, key=lambda x: x['name'].lower()),
                "custom_fields_profile_slug": PROFILE_SLUG,
            })
        return context

    @property
    @memoized
    def form(self):
        if self.request.method == "POST":
            return CustomDataFieldsForm(self.request.POST)
        else:
            return CustomDataFieldsForm({
                'data_fields': json.dumps([
                    field.to_dict()
                    for field in self.get_definition().get_fields()
                ]),
                'profiles': json.dumps([
                    profile.to_json()
                    for profile in self.get_profiles()
                ]),
            })

    def is_managed_by_upstream_domain(self):
        fields = self.get_definition().get_fields()
        return any(f.upstream_id for f in fields)

    def can_edit_linked_data(self):
        return self.request.couch_user.can_edit_linked_data(self.domain)

    def post(self, request, *args, **kwargs):
        self.save_data(request)
        return self.get(request, *args, **kwargs)

    def save_data(self, request):
        if self.form.is_valid():
            field_errors = self.save_custom_fields()
            if field_errors:
                for error in field_errors:
                    messages.error(request, error)
                return

            profile_errors = self.save_profiles()
            for error in profile_errors:
                messages.error(request, error)

            if self.show_purge_existing and self.form.cleaned_data['purge_existing']:
                self.update_existing_models()
            if self.show_profiles:
                msg = _("{} fields and profiles saved successfully.").format(self.entity_string)
            else:
                msg = _("{} fields saved successfully.").format(self.entity_string)
            messages.success(request, msg)
        else:
            if self.show_profiles:
                msg = _("Unable to save {} fields or profiles, see errors below.").format(
                    self.entity_string.lower()
                )
            else:
                msg = _("Unable to save {} fields, see errors below.").format(self.entity_string.lower())
            messages.error(request, msg)

    def update_existing_models(self):
        """
        Subclasses with show_purge_exiting set to True should override this to update existing models
        """
        raise NotImplementedError()
