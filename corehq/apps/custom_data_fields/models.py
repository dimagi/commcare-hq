import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext as _

from corehq.apps.es.users import UserES

CUSTOM_DATA_FIELD_PREFIX = "data-field"
# If mobile-worker is demo, this will be set to value 'demo'
COMMCARE_USER_TYPE_KEY = 'user_type'
COMMCARE_USER_TYPE_DEMO = 'demo'
COMMCARE_PROJECT = "commcare_project"

# This stores the id of the user's CustomDataFieldsProfile, if any
PROFILE_SLUG = "commcare_profile"

# Any new fields should use the system prefix defined by SYSTEM_PREFIX.
# SYSTEM_FIELDS is a list of fields predating SYSTEM_PREFIX that are exempt from that convention.
SYSTEM_FIELDS = ("commtrack-supply-point", 'name', 'type', 'owner_id', 'external_id', 'hq_user_id',
                 COMMCARE_USER_TYPE_KEY)
SYSTEM_PREFIX = "commcare"


def validate_reserved_words(slug):
    if slug in SYSTEM_FIELDS:
        raise ValidationError(_('You may not use "{}" as a field name').format(slug))
    for prefix in [SYSTEM_PREFIX, 'xml']:
        if slug and slug.startswith(prefix):
            raise ValidationError(_('Field names may not begin with "{}"').format(prefix))


def is_system_key(slug):
    try:
        validate_reserved_words(slug)
    except ValidationError:
        return True
    return False


class Field(models.Model):
    slug = models.CharField(max_length=127)
    is_required = models.BooleanField(default=False)
    label = models.CharField(max_length=255)
    choices = models.JSONField(default=list, null=True)
    regex = models.CharField(max_length=127, null=True)
    regex_msg = models.CharField(max_length=255, null=True)
    definition = models.ForeignKey('CustomDataFieldsDefinition', on_delete=models.CASCADE)
    # NOTE: This id will not necessarily be reliable to trace back to a parent
    #  because saving custom data overwrites the previous fields
    #  This is intended to allow us to know when downstream data is being modified
    upstream_id = models.CharField(max_length=32, null=True)

    class Meta:
        order_with_respect_to = "definition"

    def validate_choices(self, value):
        if self.choices and value and str(value) not in self.choices:
            return _(
                "'{value}' is not a valid choice for {label}. The available "
                "options are: {options}."
            ).format(
                value=value,
                label=self.label,
                options=', '.join(self.choices),
            )

    def validate_regex(self, value):
        if self.regex and value and not re.search(self.regex, value):
            return _("'{value}' is not a valid match for {label}").format(
                value=value, label=self.label)

    def validate_required(self, value):
        if self.is_required and not value:
            return _(
                "{label} is required."
            ).format(
                label=self.label
            )

    def to_dict(self):
        from django.forms.models import model_to_dict
        return model_to_dict(self, exclude=['definition', 'id'])

    def __repr__(self):
        return f'Field ({self.slug})'


class CustomDataFieldsDefinition(models.Model):
    field_type = models.CharField(max_length=126)
    domain = models.CharField(max_length=255, null=True)

    class Meta:
        unique_together = ('domain', 'field_type')

    @classmethod
    def get(cls, domain, field_type):
        return cls.objects.filter(domain=domain, field_type=field_type).first()

    @classmethod
    def get_or_create(cls, domain, field_type):
        existing = cls.get(domain, field_type)
        if existing:
            return existing
        else:
            new = cls(domain=domain, field_type=field_type)
            new.save()
            return new

    # Gets ordered, and optionally filtered, fields
    def get_fields(self, required_only=False, include_system=True):
        def _is_match(field):
            return not (
                (required_only and not field.is_required)
                or (not include_system and is_system_key(field.slug))
            )
        order = self.get_field_order()
        fields = [Field.objects.get(id=o) for o in order]
        return [f for f in fields if _is_match(f)]

    # Note that this does not save
    def set_fields(self, fields):
        self.field_set.all().delete()
        self.field_set.set(fields, bulk=False)
        self.set_field_order([f.id for f in fields])

    def get_profiles(self):
        return list(CustomDataFieldsProfile.objects.filter(definition=self).order_by(Lower('name')))

    def get_validator(self):
        """
        Returns a validator to be used in bulk import
        """
        def validate_custom_fields(custom_fields, profile=None):
            errors = []
            # Fields set via profile can be skipped since they
            #   are valdiated when the profile is created/edited
            skip_fields = profile.fields.keys() if profile else []
            fields = [f for f in self.get_fields() if f.slug not in skip_fields]
            for field in fields:
                value = custom_fields.get(field.slug, None)
                errors.append(field.validate_required(value))
                errors.append(field.validate_choices(value))
                errors.append(field.validate_regex(value))
            return ' '.join(filter(None, errors))

        return validate_custom_fields

    def get_model_and_uncategorized(self, data_dict):
        """
        Splits data_dict into two dictionaries:
        one for data which matches the model and one for data that doesn't
        Does not include reserved fields.
        """
        if not data_dict:
            return {}, {}
        model_data = {}
        uncategorized_data = {}
        slugs = {field.slug for field in self.field_set.all()}
        for k, v in data_dict.items():
            if k in slugs:
                model_data[k] = v
            elif is_system_key(k):
                pass
            else:
                uncategorized_data[k] = v

        return model_data, uncategorized_data


class CustomDataFieldsProfile(models.Model):
    name = models.CharField(max_length=126)
    fields = models.JSONField(default=dict, null=True)
    definition = models.ForeignKey('CustomDataFieldsDefinition', on_delete=models.CASCADE)
    upstream_id = models.CharField(max_length=32, null=True)

    @property
    def has_users_assigned(self):
        return bool(self._user_query().count())

    def user_ids_assigned(self):
        return self._user_query().values_list('_id', flat=True)

    def _user_query(self):
        return (
            UserES().domain(self.definition.domain)
                    .mobile_users()
                    .show_inactive()
                    .user_data(PROFILE_SLUG, self.id)
        )

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'fields': self.fields,
            'upstream_id': self.upstream_id,
        }
