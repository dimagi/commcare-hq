from __future__ import absolute_import
from couchdbkit.ext.django.schema import *
from dimagi.ext.jsonobject import USecDateTimeMeta, \
    USecDateTimeProperty
from dimagi.utils.couch.database import SafeSaveDocument


DateTimeProperty = USecDateTimeProperty


class Document(Document):
    Meta = USecDateTimeMeta


class DocumentSchema(DocumentSchema):
    Meta = USecDateTimeMeta


class SafeSaveDocument(SafeSaveDocument):
    Meta = USecDateTimeMeta
