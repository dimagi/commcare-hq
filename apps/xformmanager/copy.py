from __future__ import absolute_import

import copy

from django.db.models.query import CollectedObjects
from django.utils.datastructures import SortedDict

def collect_related(obj):
    """Collect all related objects to a single object by traversing
       ForgeignKeys.  Useful if you are about to delete something 
       and see what's being affected, or if you need to migrate a
       collection of objects.
    """
    collected_objs = CollectedObjects()
    obj._collect_sub_objects(collected_objs)
    return collected_objs 

def copy_related(collection):
    """
    Take in a CollectedObjects object and convert all the 
    query sets to explicit instantiations (copies) of the 
    objects.
    """
    to_return = SortedDict()
    for cls, objs in collection.items():
        copied_items = {}
        for pk, item in objs.items():
            copied_items[pk] = copy.copy(item)
        to_return[cls] = copied_items
    return to_return
