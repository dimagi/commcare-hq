"""
MOTECH modules can update the `serializers` dictionary to register
their own serializer functions.

They would do something like the following::

    from corehq.motech.serializers import serializers
    serializers.update({
        (from_data_type, to_data_type): serializer_function,
    })

Serializer functions accept a value in `from_data_type`, and return a
value in `to_data_type`.

"""
from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
)


def to_decimal(value):
    try:
        return float(value)
    except ValueError:
        return None


def to_integer(value):
    try:
        return int(value)
    except ValueError:
        return None


def to_text(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        return str(value)
    return value


serializers = {
    # (from_data_type, to_data_type): function
    (None, COMMCARE_DATA_TYPE_DECIMAL): to_decimal,
    (None, COMMCARE_DATA_TYPE_INTEGER): to_integer,
    (None, COMMCARE_DATA_TYPE_TEXT): to_text,
}
