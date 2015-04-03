from __future__ import absolute_import
from couchdbkit.ext.django.schema import *
from corehq.ext.jsonobject import TransDateTimeMeta, \
    TransitionalExactDateTimeProperty
from dimagi.utils.couch.database import SafeSaveDocument

# USec stands for microsecond
USecDateTimeProperty = TransitionalExactDateTimeProperty


class USecDocument(Document):
    Meta = TransDateTimeMeta


class USecDocumentSchema(DocumentSchema):
    Meta = TransDateTimeMeta


class USecSafeSaveDocument(SafeSaveDocument):
    Meta = TransDateTimeMeta
