"""
CaseSearchES
------

.. code-block:: python

from corehq.apps.es import case_search as case_search_es

    q = (case_search_es.CaseSearchES()
         .domain('testproject')
"""
from .es_query import HQESQuery
from . import filters

from corehq.pillows.const import CASE_SEARCH_ALIAS


class CaseSearchES(HQESQuery):
    index = CASE_SEARCH_ALIAS

    @property
    def builtin_filters(self):
        return [case_property] + super(CaseSearchES, self).builtin_filters


def case_property(key, value):
    path = "case_properties"
    return filters.nested(
        path,
        filters.AND(
            filters.term("{}.key".format(path), key),
            filters.term("{}.value".format(path), value),
        )
    )
