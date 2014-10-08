from __future__ import absolute_import
from corehq.ext.jsonobject import ISOMeta, GeoPointProperty, UTCDateTimeProperty
from couchdbkit import Document, DocumentSchema
from dimagi.utils.couch.database import SafeSaveDocument

__all__ = [
    'GeoPointProperty',
    'UTCDateTimeProperty',
    'SafeSaveDocument',
    'ISODocument',
    'ISODocumentSchema',
    'ISOSafeSaveDocument',
]


class ISODocument(Document):
    Meta = ISOMeta


class ISODocumentSchema(DocumentSchema):
    Meta = ISOMeta


class ISOSafeSaveDocument(SafeSaveDocument):
    Meta = ISOMeta
