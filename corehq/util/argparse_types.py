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


def validate_integer(gt=None, lt=None):
    """Return argparser action to validate integer inputs:

    parser.add_argument('--count', action=validate_integer(gt=0, lt=11), help="Integer between 1 and 10")
    """

    class ValidateIntegerRange(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            try:
                values = int(values)
            except ValueError:
                raise argparse.ArgumentError(self, f"Invalid integer: {values}")

            if gt is not None and gt >= values:
                raise argparse.ArgumentError(self, f"Must be greater than {gt}")

            if lt is not None and lt <= values:
                raise argparse.ArgumentError(self, f"Must be less than than {lt}")

            setattr(namespace, self.dest, values)

    return ValidateIntegerRange
