from couchdbkit.ext.django.schema import (Document, StringProperty,
    BooleanProperty, SchemaListProperty)
from jsonobject import JsonObject


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
        ).one()

        if existing:
            return existing
        else:
            new = cls(domain=domain, field_type=field_type)
            new.save()
            return new

    def validate_custom_fields(self, custom_fields):
        """
        Returns a dict with a list of keys that have
        any of the various error possibilities:

        Example:
        {
            'missing_keys': ['dob']
            'invalid_choice': ['gender']
        }
        """
        errors = {'missing_keys': []}
        for field in self.fields:
            if field.is_required and not custom_fields.get(field.slug, None):
                errors['missing_keys'].append(field.slug)

        return errors
