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
from __future__ import absolute_import

from __future__ import unicode_literals
import six

from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
)
from corehq.util.python_compatibility import soft_assert_type_text


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
    if not isinstance(value, six.string_types):
        return six.text_type(value)
    soft_assert_type_text(value)
    return value


serializers = {
    # (from_data_type, to_data_type): function
    (None, COMMCARE_DATA_TYPE_DECIMAL): to_decimal,
    (None, COMMCARE_DATA_TYPE_INTEGER): to_integer,
    (None, COMMCARE_DATA_TYPE_TEXT): to_text,
}
