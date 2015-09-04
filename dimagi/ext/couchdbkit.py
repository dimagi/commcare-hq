from __future__ import absolute_import
from couchdbkit.ext.django.schema import *
from dimagi.ext.jsonobject import USecDateTimeMeta, \
    DateTimeProperty, OldDateTimeProperty
from dimagi.utils.couch.database import SafeSaveDocument

__all__ = ['Property', 'StringProperty', 'IntegerProperty',
            'DecimalProperty', 'BooleanProperty', 'FloatProperty',
            'DateTimeProperty', 'DateProperty', 'TimeProperty',
            'dict_to_json', 'list_to_json', 'value_to_json',
            'dict_to_python', 'list_to_python',
            'convert_property', 'DocumentSchema', 'Document',
            'SchemaProperty', 'SchemaListProperty', 'ListProperty',
            'DictProperty', 'StringDictProperty', 'StringListProperty',
            'SchemaDictProperty', 'SetProperty', 'SafeSaveDocument']


OldDateTimeProperty = OldDateTimeProperty
OldDocument = Document
OldDocumentSchema = DocumentSchema
OldSafeSaveDocument = SafeSaveDocument

DateTimeProperty = DateTimeProperty


class Document(OldDocument):
    Meta = USecDateTimeMeta


class DocumentSchema(OldDocumentSchema):
    Meta = USecDateTimeMeta


class SafeSaveDocument(OldSafeSaveDocument):
    Meta = USecDateTimeMeta
