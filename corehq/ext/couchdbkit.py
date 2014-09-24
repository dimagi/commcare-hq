from __future__ import absolute_import
from corehq.ext.jsonobject import ISOMeta, GeoPointProperty, ISO8601Property
from couchdbkit import Document, DocumentSchema
from dimagi.utils.couch.database import SafeSaveDocument

__all__ = [
    'GeoPointProperty',
    'ISO8601Property',
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
