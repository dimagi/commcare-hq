from couchdbkit.ext.django.schema import (Document, StringProperty,
    BooleanProperty, SchemaListProperty)
from jsonobject import JsonObject
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _


CUSTOM_DATA_FIELD_PREFIX = "data-field"
# This list is used to grandfather in existing data, any new fields should use
# the system prefix defined below
SYSTEM_FIELDS = ["commtrack-supply-point"]
SYSTEM_PREFIX = "commcare"


def validate_reserved_words(value):
    if value in SYSTEM_FIELDS:
        raise ValidationError(_('You may not use "{}" as a field name')
                              .format(value))
    for prefix in [SYSTEM_PREFIX, 'xml']:
        if value.startswith(prefix):
            raise ValidationError(_('Field names may not begin with "{}"')
                                  .format(prefix))



class CustomDataField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty()
    label = StringProperty()
    is_system = BooleanProperty()


class CustomDataFieldsDefinition(Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    field_type = StringProperty()
    base_doc = "CustomDataFieldsDefinition"
    domain = StringProperty()
    _fields = SchemaListProperty(CustomDataField)

    def get_fields(self, required_only=False, include_system=False):
        def _is_match(field):
            if required_only and not field.is_required:
                return False
            if not include_system and field.is_system:
                return False
            return True
        return filter(_is_match, self._fields)

    def has_fields(self):
        return bool(self.get_fields())

    def set_fields(self, fields):
        system_fields = [f for f in self._fields if f.is_system]
        self._fields = fields + system_fields

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
        def validate_custom_fields(custom_fields):
            errors = []
            missing_keys = []
            for field in self.get_fields():
                if field.is_required and not custom_fields.get(field.slug, None):
                    missing_keys.append(field.slug)
            if missing_keys:
                errors.append(_(
                    "Cannot create or update a {entity} without "
                    "the required field(s): {fields}."
                ).format(
                    entity=data_field_class.entity_string,
                    fields=', '.join(missing_keys)
                ))
            return ' '.join(errors)

        return validate_custom_fields
