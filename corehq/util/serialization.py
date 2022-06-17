from decimal import Decimal

import simplejson


def deserialize_decimal(serialized_value):
    deserialized_value = simplejson.loads(serialized_value)
    if not isinstance(deserialized_value, Decimal):
        # there are cases (whole numbers), where simplejson does not load the value back as a Decimal
        # so we need to coerce the value to be a Decimal
        deserialized_value = Decimal(deserialized_value)

    return deserialized_value
