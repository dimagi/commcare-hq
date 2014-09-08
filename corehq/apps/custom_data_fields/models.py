from couchdbkit.ext.django.schema import (Document, StringProperty,
    BooleanProperty, SchemaListProperty)
from jsonobject import JsonObject


CUSTOM_DATA_FIELD_PREFIX = "data-field"

class CustomDataField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty()
    label = StringProperty()

    @property
    def html_slug(self):
        return "{}{}".format(CUSTOM_DATA_FIELD_PREFIX, self.slug)


class CustomDataFieldsDefinition(Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    doc_type = StringProperty()
    base_doc = "CustomDataFieldsDefinition"
    domain = StringProperty()
    fields = SchemaListProperty(CustomDataField)

    @classmethod
    def by_domain(cls, domain, doc_type):
        return cls.view(
            'custom_data_fields/by_doc_type',
            key=[domain, doc_type],
            include_docs=True,
            reduce=False,
        ).first()
