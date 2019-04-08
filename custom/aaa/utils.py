from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import connections

from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.sql_db.connections import get_aaa_db_alias
from custom.aaa.const import MINISTRY_MOHFW, MINISTRY_MWCD, ALL
from custom.aaa.models import AggAwc, AggVillage, CcsRecord, Child, Woman


def build_location_filters(location_id, ministry, with_child=True):
    try:
        location = SQLLocation.objects.get(location_id=location_id)
    except SQLLocation.DoesNotExist:
        if not with_child:
            return {}
        return {'state_id': 'ALL'}

    location_ancestors = location.get_ancestors(include_self=True)

    filters = {
        "{}_id".format(ancestor.location_type.code): ancestor.location_id
        for ancestor in location_ancestors
    }

    if not with_child:
        return filters

    location_type = location.location_type

    params = dict(
        domain=location_type.domain
    )

    if location_type.code == 'district' and ministry == MINISTRY_MOHFW:
        params.update(dict(code='taluka'))
    elif location_type.code == 'district' and ministry == MINISTRY_MWCD:
        params.update(dict(code='block'))
    else:
        params.update(dict(parent_type=location_type))
    child_location_type = LocationType.objects.filter(**params).first()
    if child_location_type is not None:
        filters["{}_id".format(child_location_type.code)] = ALL

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
    db_alias = get_aaa_db_alias()
    with connections[db_alias].cursor() as cursor:
        cursor.execute('explain ' + agg_query, agg_params)
        return cls.__name__ + method.__name__, cursor.fetchall()


def get_location_model_for_ministry(ministry):
    if ministry == 'MoHFW':
        return AggVillage
    elif ministry == 'MWCD':
        return AggAwc

    # This should be removed eventually once ministry is reliably being passed back from front end
    return AggVillage
