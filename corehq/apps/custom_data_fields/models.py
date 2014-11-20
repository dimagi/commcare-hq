from couchdbkit.ext.django.schema import (Document, StringProperty,
    BooleanProperty, SchemaListProperty)
from jsonobject import JsonObject
from django.utils.translation import ugettext as _


CUSTOM_DATA_FIELD_PREFIX = "data-field"


class CustomDataField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty()
    label = StringProperty()


class CustomDataFieldsDefinition(Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    field_type = StringProperty()
    base_doc = "CustomDataFieldsDefinition"
    domain = StringProperty()
    fields = SchemaListProperty(CustomDataField)

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
            for field in self.fields:
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
