from couchdbkit.ext.django.schema import (Document, StringProperty,
    BooleanProperty, SchemaListProperty, StringListProperty)
from jsonobject import JsonObject
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _


CUSTOM_DATA_FIELD_PREFIX = "data-field"
# This list is used to grandfather in existing data, any new fields should use
# the system prefix defined below
SYSTEM_FIELDS = ["commtrack-supply-point"]
SYSTEM_PREFIX = "commcare"


def _validate_reserved_words(slug):
    if slug in SYSTEM_FIELDS:
        return _('You may not use "{}" as a field name').format(slug)
    for prefix in [SYSTEM_PREFIX, 'xml']:
        if slug and slug.startswith(prefix):
            return _('Field names may not begin with "{}"').format(prefix)


def is_system_key(slug):
    return bool(_validate_reserved_words(slug))


def validate_reserved_words(slug):
    error = _validate_reserved_words(slug)
    if error is not None:
        raise ValidationError(error)


class CustomDataField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty()
    label = StringProperty()
    choices = StringListProperty()


class CustomDataFieldsDefinition(Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    field_type = StringProperty()
    base_doc = "CustomDataFieldsDefinition"
    domain = StringProperty()
    fields = SchemaListProperty(CustomDataField)

    def get_fields(self, required_only=False):
        def _is_match(field):
            if required_only and not field.is_required:
                return False
            return True
        return filter(_is_match, self.fields)

    @classmethod
    def get_or_create(cls, domain, field_type):
        existing = cls.view(
            'custom_data_fields/by_field_type',
            key=[domain, field_type],
            include_docs=True,
            reduce=False,
            # if there's more than one,
            # it's probably because a few were created at the same time
            # due to a race condition
            # todo: a better solution might be to use locking in this code
            limit=1,
        ).one()

        if existing:
            return existing
        else:
            new = cls(domain=domain, field_type=field_type)
            new.save()
            return new

    # TODO use this in the CustomDataEditor too?
    def get_validator(self, data_field_class):
        """
        Returns a validator to be used in bulk import
        """
        def validate_choices(field, value):
            if field.choices and value and value not in field.choices:
                return _(
                    "'{value}' is not a valid choice for {slug}, the available "
                    "options are: {options}."
                ).format(
                    value=value,
                    slug=field.slug,
                    options=', '.join(field.choices),
                )

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
            return ' '.join(filter(None, errors))

        return validate_custom_fields
