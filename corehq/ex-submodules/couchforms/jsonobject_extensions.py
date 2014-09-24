from decimal import Decimal
from couchdbkit import Document, DocumentSchema
import datetime
import iso8601
from jsonobject import JsonProperty, DateTimeProperty
from jsonobject.exceptions import BadValueError
from .datatypes import GeoPoint
from dimagi.utils.couch.database import SafeSaveDocument


def _canonical_decimal(n):
    """
    raises ValueError for non-canonically formatted decimal strings

    example: '00.1' or '.1' whose canonical form is '0.1'

    """
    decimal = Decimal(n)
    if unicode(decimal) != n:
        raise ValueError('{!r} is not a canonically formatted decimal')
    return decimal


class GeoPointProperty(JsonProperty):
    """
    wraps a GeoPoint object where the numbers are represented as Decimals
    to preserve exact formatting (number of decimal places, etc.)

    """

    def wrap(self, obj):
        try:
            return GeoPoint(*[_canonical_decimal(n) for n in obj.split(' ')])
        except (ValueError, TypeError):
            raise BadValueError("{!r} is not a valid format GeoPoint format"
                                .format(obj))

    def unwrap(self, obj):
        return obj, '{} {} {} {}'.format(*obj)


class ISO8601Property(DateTimeProperty):
    def __init__(self, **kwargs):
        if 'exact' in kwargs:
            assert kwargs['exact'] is True
        kwargs['exact'] = True
        super(ISO8601Property, self).__init__(**kwargs)

    def wrap(self, obj):
        dt = iso8601.parse_date(obj)
        return dt.astimezone(iso8601.iso8601.UTC).replace(tzinfo=None)


class ISOMeta(object):
    update_properties = {datetime.datetime: ISO8601Property}


class ISODocument(Document):
    Meta = ISOMeta


class ISODocumentSchema(DocumentSchema):
    Meta = ISOMeta


class ISOSafeSaveDocument(SafeSaveDocument):
    Meta = ISOMeta
