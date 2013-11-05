from datetime import datetime

COUCH_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
EXCEL_FORMAT = '%Y-%m-%d %H:%M:%S'


def identity(val, doc):
    return val


def auto_format_datetime(expected_format, output_format, val, doc):
    if isinstance(val, basestring):
        try:
            return datetime.strptime(val, expected_format).strftime(output_format)
        except ValueError:
            pass
    return val


def couch_to_excel_datetime(val, doc):
    return auto_format_datetime(COUCH_FORMAT, EXCEL_FORMAT, val, doc)
