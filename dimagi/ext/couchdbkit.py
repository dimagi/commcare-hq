from __future__ import absolute_import
from couchdbkit.ext.django.schema import *
from dimagi.ext.jsonobject import USecDateTimeMeta, \
    DateTimeProperty, OldDateTimeProperty
from dimagi.utils.couch.database import SafeSaveDocument


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
