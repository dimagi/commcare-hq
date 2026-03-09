import datetime
from decimal import Decimal, InvalidOperation


def coerce_to_date(value):
    """Parse a date string, returning a ``datetime.date`` or ``None``.

    Accepts ISO format: ``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SS``.
    Returns ``None`` for invalid, empty, or ``None`` input.
    """
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def coerce_to_number(value):
    """Parse a numeric string, returning a ``Decimal`` or ``None``.

    Returns ``None`` for invalid, empty, or ``None`` input.
    """
    if not value or not str(value).strip():
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None
