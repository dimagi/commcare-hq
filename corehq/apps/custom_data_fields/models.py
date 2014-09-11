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
    def by_domain(cls, domain, field_type):
        return cls.view(
            'custom_data_fields/by_field_type',
            key=[domain, field_type],
            include_docs=True,
            reduce=False,
        ).one()
