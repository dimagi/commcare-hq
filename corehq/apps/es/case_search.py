"""
CaseSearchES
------

.. code-block:: python

from corehq.apps.es import case_search as case_search_es

    q = (case_search_es.CaseSearchES()
         .domain('testproject')
"""
from . import filters, queries
from .es_query import HQESQuery

from corehq.pillows.const import CASE_SEARCH_ALIAS


PATH = "case_properties"


class CaseSearchES(HQESQuery):
    index = CASE_SEARCH_ALIAS

    @property
    def builtin_filters(self):
        return [case_property_filter] + super(CaseSearchES, self).builtin_filters

    @property
    def _case_property_queries(self):
        """
        Returns all current case_property queries
        """
        try:
            return self.es_query['query']['filtered']['query']['bool']['must']
        except (KeyError, TypeError):
            return []

    def case_property_query(self, key, value):
        """
        Search for a case property. Will overwrite other queries set with set_query unless they are 'must's
        """
        # Filter by case_properties.key and do a text search in case_properties.value
        new_query = queries.nested(
            PATH,
            queries.filtered(
                queries.search_string_query(value, default_fields=["{}.value".format(PATH)]),
                filters.term("{}.key".format(PATH), key)
            )
        )
        return self.set_query(
            queries.BOOL(
                queries.MUST(
                    [new_query] + self._case_property_queries
                )
            )
        )


def case_property_filter(key, value):
    return filters.nested(
        PATH,
        filters.AND(
            filters.term("{}.key".format(PATH), key),
            filters.term("{}.value".format(PATH), value),
        )
    )
