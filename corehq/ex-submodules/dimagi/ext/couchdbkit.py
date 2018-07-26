from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit.ext.django.schema import *
from dimagi.ext.jsonobject import USecDateTimeMeta, \
    DateTimeProperty, OldDateTimeProperty
from dimagi.utils.couch.database import SafeSaveDocument

from corehq.util.soft_assert import soft_assert

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


_couch_attachment_soft_assert = soft_assert(
    to='{}@{}'.format('npellegrino', 'dimagi.com'),
    exponential_backoff=False,
)


class Document(OldDocument):
    Meta = USecDateTimeMeta

    def put_attachment(self, *args, **kwargs):
        _couch_attachment_soft_assert(False, 'Document.put_attachment was called')
        super(Document, self).put_attachment(*args, **kwargs)

    def fetch_attachment(self, *args, **kwargs):
        _couch_attachment_soft_assert(False, 'Document.fetch_attachment was called')
        super(Document, self).fetch_attachment(*args, **kwargs)

    def delete_attachment(self, *args, **kwargs):
        _couch_attachment_soft_assert(False, 'Document.delete_attachment was called')
        super(Document, self).delete_attachment(*args, **kwargs)


class DocumentSchema(OldDocumentSchema):
    Meta = USecDateTimeMeta


class SafeSaveDocument(OldSafeSaveDocument):
    Meta = USecDateTimeMeta

    def put_attachment(self, *args, **kwargs):
        _couch_attachment_soft_assert(False, 'SafeSaveDocument.put_attachment was called')
        super(SafeSaveDocument, self).put_attachment(*args, **kwargs)

    def fetch_attachment(self, *args, **kwargs):
        _couch_attachment_soft_assert(False, 'SafeSaveDocument.fetch_attachment was called')
        super(SafeSaveDocument, self).fetch_attachment(*args, **kwargs)

    def delete_attachment(self, *args, **kwargs):
        _couch_attachment_soft_assert(False, 'SafeSaveDocument.delete_attachment was called')
        super(SafeSaveDocument, self).delete_attachment(*args, **kwargs)
