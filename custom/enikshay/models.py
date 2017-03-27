import math
from django.db import models


class IssuerId(models.Model):
    """
    This model is used to ensure unique, incrementing issuer IDs for users,
    and to look up a user given an issuer ID.
    obj.pk represents the serial issuer ID, later representations will be added as fields
    """
    domain = models.CharField(max_length=255, db_index=True)
    user_id = models.CharField(max_length=50, db_index=True, unique=True)


def compress_id(serial_id, growth_symbols, lead_symbols, body_symbols, body_digit_count):
    if not growth_symbols or not lead_symbols:
        raise AssertionError("We need both growth and lead symbols")

    if set(growth_symbols) & set(lead_symbols):
        raise AssertionError("You cannot use the same symbol as both a growth and a lead")

    lead_digit_base = len(lead_symbols)
    growth_digit_base = len(growth_symbols)
    body_digit_base = len(body_symbols)
    max_fixed_length_size = (body_digit_base ** body_digit_count) * lead_digit_base

    if serial_id >= max_fixed_length_size:
        times_over_max = serial_id / max_fixed_length_size
        growth_digit_count = int(math.log(times_over_max, growth_digit_base)) + 1
    else:
        growth_digit_count = 0

    digit_bases = ([growth_digit_base] * growth_digit_count
                   + [lead_digit_base]
                   + [body_digit_base] * body_digit_count)

    divisors = [1]
    for digit_base in reversed(digit_bases[1:]):
        divisors.insert(0, divisors[0] * digit_base)

    remainder = serial_id
    counts = []
    for divisor in divisors:
        counts.append(remainder / divisor)
        remainder = remainder % divisor

    if remainder != 0:
        raise AssertionError("Failure while encoding ID {}!".format(serial_id))

    output = []
    for i, count in enumerate(counts):
        if i < growth_digit_count:
            output.append(growth_symbols[count])
        elif i == growth_digit_count:
            output.append(lead_symbols[count])
        else:
            output.append(body_symbols[count])
    return ''.join(output)
