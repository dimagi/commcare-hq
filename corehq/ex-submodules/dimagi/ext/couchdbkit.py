from couchdbkit.ext.django.schema import *
from dimagi.ext.jsonobject import USecDateTimeMeta, \
    DateTimeProperty, OldDateTimeProperty
from dimagi.utils.couch.database import SafeSaveDocument

__all__ = [
    'Property', 'StringProperty', 'IntegerProperty',
    'DecimalProperty', 'BooleanProperty', 'FloatProperty',
    'DateTimeProperty', 'DateProperty', 'TimeProperty',
    'dict_to_json', 'list_to_json', 'value_to_json',
    'dict_to_python', 'list_to_python',
    'convert_property', 'DocumentSchema', 'Document',
    'SchemaProperty', 'SchemaListProperty', 'ListProperty',
    'DictProperty', 'StringDictProperty', 'StringListProperty',
    'SchemaDictProperty', 'SetProperty', 'SafeSaveDocument',
]


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


# A formatter configured in HQ settings (`couch-request-formatter`) logs
# extra metrics provided by this logger to a file that can be consumed
# for couch request timing analysis.
from couchdbkit.logging import install_request_logger as _install_logger
_install_logger()
