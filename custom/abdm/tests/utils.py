from django.utils.dateparse import parse_datetime


def convert_utc_iso_to_datetime(date_str):
    """Converts utc iso format to python datetime without timezone for comparison with model datetime fields"""
    return parse_datetime(date_str).replace(tzinfo=None)
