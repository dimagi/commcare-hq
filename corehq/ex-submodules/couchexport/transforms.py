import datetime

COUCH_FORMATS = ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S.%fZ']
EXCEL_FORMAT = '%Y-%m-%d %H:%M:%S'


def identity(val, doc):
    return val


def couch_to_excel_datetime(val, doc):
    if isinstance(val, basestring):
        # todo: subtree merge couchexport into commcare-hq
        # todo: and replace this with iso_string_to_datetime
        dt_val = None
        for fmt in COUCH_FORMATS:
            try:
                dt_val = datetime.datetime.strptime(val, fmt)
            except ValueError:
                pass
            else:
                break
        if dt_val is not None:
            try:
                return dt_val.strftime(EXCEL_FORMAT)
            except ValueError:
                pass
    return val
