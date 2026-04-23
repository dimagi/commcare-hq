from collections import namedtuple

ExportLoggingContext = namedtuple('ExportLoggingContext', [
    'download_id',
    'username',
    'trigger',
    'filters',
    'bulk',
])


def build_filter_summary(filters):
    """Serialize an ExportInstanceFilters schema to a flat dict for logging.

    Uses DocumentSchema.properties() to dynamically discover fields,
    so new filter properties are automatically included.
    """
    if filters is None:
        return {}
    result = {}
    for name in type(filters).properties():
        if name == 'doc_type':
            continue
        value = getattr(filters, name)
        result[name] = value.to_json() if hasattr(value, 'to_json') else value
    return result
