from decimal import Decimal


def serialize(value):
    """
    Serializes a value so it can properly be parsed into XML
    """
    if isinstance(value, (int, Decimal, float, long)):
        return unicode(value)
    else:
        return value if value is not None else ""
