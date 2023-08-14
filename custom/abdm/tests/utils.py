import json
from django.utils.dateparse import parse_datetime


def json_from_file(file_path):
    with open(file_path) as file:
        return json.load(file)


def convert_utc_iso_to_datetime(date_str):
    """Converts utc iso format to python datetime without timezone for comparison with model datetime fields"""
    return parse_datetime(date_str).replace(tzinfo=None)
