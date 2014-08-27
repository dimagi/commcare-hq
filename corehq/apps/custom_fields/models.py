from couchdbkit.ext.django.schema import (Document, StringProperty,
    BooleanProperty, SchemaListProperty)
from jsonobject import JsonObject


class CustomField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty()
    label = StringProperty()


class CustomFieldsDefinition(Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    doc_type = StringProperty()
    base_doc = "CustomFieldsDefinition"
    domain = StringProperty()
    fields = SchemaListProperty(CustomField)

    @classmethod
    def by_domain(cls, domain, doc_type):
        doc = cls.view(
            'custom_fields/by_doc_type',
            key=[domain, doc_type],
            include_docs=True,
            reduce=False,
        ).first()

        return doc
