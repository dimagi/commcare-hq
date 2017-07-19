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
