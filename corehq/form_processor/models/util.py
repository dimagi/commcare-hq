from collections import namedtuple
from functools import lru_cache
from itertools import groupby

from corehq.util.metrics import metrics_counter


def fetchall_as_namedtuple(cursor):
    "Return all rows from a cursor as a namedtuple generator"
    Result = _get_result_tuple(tuple(col[0] for col in cursor.description))
    return (Result(*row) for row in cursor)


@lru_cache
def _get_result_tuple(names):
    metrics_counter("commcare.lru.result_tuple.cachemiss")
    return namedtuple('Result', names)


def sort_with_id_list(object_list, id_list, id_property):
    """Sort object list in the same order as given list of ids

    SQL does not necessarily return the rows in any particular order so
    we need to order them ourselves.

    NOTE: this does not return the sorted list. It sorts `object_list`
    in place using Python's built-in `list.sort`.
    """
    def key(obj):
        return index_map[getattr(obj, id_property)]

    index_map = {id_: index for index, id_ in enumerate(id_list)}
    object_list.sort(key=key)


def attach_prefetch_models(objects_by_id, prefetched_models, link_field_name, cached_attrib_name):
    prefetched_groups = groupby(prefetched_models, lambda x: getattr(x, link_field_name))
    seen = set()
    for obj_id, group in prefetched_groups:
        seen.add(obj_id)
        obj = objects_by_id[obj_id]
        setattr(obj, cached_attrib_name, list(group))

    unseen = set(objects_by_id) - seen
    for obj_id in unseen:
        obj = objects_by_id[obj_id]
        setattr(obj, cached_attrib_name, [])
