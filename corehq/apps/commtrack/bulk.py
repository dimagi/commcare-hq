from corehq.apps.commtrack.models import *


def set_error(row, msg, override=False):
    """set an error message on a stock report to be imported"""
    if override or 'error' not in row:
        row['error'] = msg
