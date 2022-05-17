import json
from datetime import timezone, datetime

from django.conf import settings

from corehq.util.es.elasticsearch import SerializationError
from corehq.util.json import CommCareJSONEncoder
from corehq.util.metrics import metrics_counter


class ElasticJSONSerializer(object):
    """Modified version of ``elasticsearch.serializer.JSONSerializer``
    that uses the CommCareJSONEncoder for serializing to JSON.
    """
    mimetype = 'application/json'

    def loads(self, s):
        try:
            return json.loads(s)
        except (ValueError, TypeError) as e:
            raise SerializationError(s, e)

    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, cls=CommCareJSONEncoder)
        except (ValueError, TypeError) as e:
            raise SerializationError(data, e)


def values_list(hits, *fields, **kwargs):
    """modeled after django's QuerySet.values_list"""
    flat = kwargs.pop('flat', False)
    if kwargs:
        raise TypeError('Unexpected keyword arguments to values_list: %s'
                        % (list(kwargs),))
    if flat and len(fields) > 1:
        raise TypeError("'flat' is not valid when values_list is called with more than one field.")
    if not fields:
        raise TypeError('must be called with at least one field')
    if flat:
        field, = fields
        return [hit.get(field) for hit in hits]
    else:
        return [tuple(hit.get(field) for field in fields) for hit in hits]


def flatten_field_dict(results, fields_property='fields'):
    """
    In ElasticSearch 1.3, the return format was changed such that field
    values are always returned as lists, where as previously they would
    be returned as scalars if the field had a single value, and returned
    as lists if the field had multiple values.
    This method restores the behavior of 0.90 .

    https://www.elastic.co/guide/en/elasticsearch/reference/1.3/_return_values.html
    """
    field_dict = results.get(fields_property, {})
    for key, val in field_dict.items():
        new_val = val
        if type(val) == list and len(val) == 1:
            new_val = val[0]
        field_dict[key] = new_val
    return field_dict


def track_es_report_load(domain, report_slug, owner_count):
    # Intended mainly for ICDs to track load of user filter counts when hitting ES
    if hasattr(settings, 'TRACK_ES_REPORT_LOAD'):
        metrics_counter(
            'commcare.es.user_filter_count',
            owner_count,
            tags={'report_slug': report_slug, 'domain': domain}
        )


def es_format_datetime(val):
    """
    Takes a date or datetime object and converts it to a format ES can read
    (see DATE_FORMATS_ARR). Strings are returned unmodified.
    """
    if isinstance(val, str):
        return val
    elif isinstance(val, datetime) and val.microsecond and val.tzinfo:
        # We don't support microsec precision with timezones
        return val.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    else:
        return val.isoformat()
