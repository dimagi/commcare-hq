from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import connections

from corehq.apps.locations.models import LocationType, SQLLocation
from custom.aaa.models import AggAwc, AggVillage, CcsRecord, Child, Woman


def build_location_filters(location_id):
    try:
        location = SQLLocation.objects.get(location_id=location_id)
    except SQLLocation.DoesNotExist:
        return {'state_id': 'ALL'}

    location_ancestors = location.get_ancestors(include_self=True)

    filters = {
        "{}_id".format(ancestor.location_type.code): ancestor.location_id
        for ancestor in location_ancestors
    }

    location_type = location.location_type
    child_location_type = LocationType.objects.filter(domain=location_type.domain, parent_type=location_type)
    filters["{}_id".format(child_location_type.code)] = 'All'

    return filters


def explain_aggregation_queries(domain, window_start, window_end):
    queries = {}
    for cls in (AggAwc, AggVillage, CcsRecord, Child, Woman):
        for agg_query in cls.aggregation_queries:
            explanation = _explain_query(cls, agg_query, domain, window_start, window_end)
            queries[explanation[0]] = explanation[1]

    return queries


def _explain_query(cls, method, domain, window_start, window_end):
    agg_query, agg_params = method(domain, window_start, window_end)
    with connections['aaa-data'].cursor() as cursor:
        cursor.execute('explain ' + agg_query, agg_params)
        return cls.__name__ + method.__name__, cursor.fetchall()
