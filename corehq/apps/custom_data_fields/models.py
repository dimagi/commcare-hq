import re

from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.translation import ugettext as _

CUSTOM_DATA_FIELD_PREFIX = "data-field"
# If mobile-worker is demo, this will be set to value 'demo'
COMMCARE_USER_TYPE_KEY = 'user_type'
COMMCARE_USER_TYPE_DEMO = 'demo'
# This list is used to grandfather in existing data, any new fields should use
# the system prefix defined below
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
    choices = JSONField(default=list, null=True)
    regex = models.CharField(max_length=127, null=True)
    regex_msg = models.CharField(max_length=255, null=True)
    definition = models.ForeignKey('CustomDataFieldsDefinition', on_delete=models.CASCADE)


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

    def get_fields(self, required_only=False, include_system=True):
        def _is_match(field):
            return not (
                (required_only and not field.is_required)
                or (not include_system and is_system_key(field.slug))
            )
        return filter(_is_match, self.sqlfield_set.all())

    # Note that this does not save
    def set_fields(self, fields):
        self.field_set.all().delete()
        self.field_set.set(fields, bulk=False)

    def get_validator(self, data_field_class):
        """
        Returns a validator to be used in bulk import
        """
        def validate_choices(field, value):
            if field.choices and value and str(value) not in field.choices:
                return _(
                    "'{value}' is not a valid choice for {slug}, the available "
                    "options are: {options}."
                ).format(
                    value=value,
                    slug=field.slug,
                    options=', '.join(field.choices),
                )

        def validate_regex(field, value):
            if field.regex and value and not re.search(field.regex, value):
                return _("'{value}' is not a valid match for {slug}").format(
                    value=value, slug=field.slug)

        def validate_required(field, value):
            if field.is_required and not value:
                return _(
                    "Cannot create or update a {entity} without "
                    "the required field: {field}."
                ).format(
                    entity=data_field_class.entity_string,
                    field=field.slug
                )

        def validate_custom_fields(custom_fields):
            errors = []
            for field in self.fields:
                value = custom_fields.get(field.slug, None)
                errors.append(validate_required(field, value))
                errors.append(validate_choices(field, value))
                errors.append(validate_regex(field, value))
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
        slugs = {field.slug for field in self.field_set}
        for k, v in data_dict.items():
            if k in slugs:
                model_data[k] = v
            elif is_system_key(k):
                pass
            else:
                uncategorized_data[k] = v

        return model_data, uncategorized_data
