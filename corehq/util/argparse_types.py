import argparse
from datetime import datetime


def utc_timestamp(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(
            "Invalid datetime specified: '%s'. "
            "Expected UTC timestamp in the format: YYYY-MM-DD HH:MM:SS" % value
        )


def date_type(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(
            "Invalid date specified: '%s'. "
            "Expected date in the format: YYYY-MM-DD" % value
        )


# NOTE: The `validate_integer` function has been renamed to `validate_range`,
# and it no longer enforces the argument type. This requires specifying the
# argument type (for non-default types) when using `action=validate_range(...)`.
# To compare, the previous function could be used as such:
#
#   parser.add_argument("value", action=validate_integer(gt=0))
#
# Using the new function, `type` must be specified as well:
#
#   parser.add_argument("value", type=int, action=validate_range(gt=0))
#
def validate_range(gt=None, lt=None):
    """Create an argparse.Action subclass for validating comparable inputs.

    :param gt: value which the argument must be greater than
    :param lt: value which the argument must be less than
    :returns: argparse.Action subclass

    Example:
    parser.add_argument('--fraction', action=validate_range(gt=0.0, lt=1.0),
        type=float, help="Number between 0 and 1")
    """

    class ValidateRange(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):

            if gt is not None and gt >= values:
                raise argparse.ArgumentError(self, f"Must be greater than {gt}")

            if lt is not None and lt <= values:
                raise argparse.ArgumentError(self, f"Must be less than {lt}")

            setattr(namespace, self.dest, values)

    return ValidateRange
