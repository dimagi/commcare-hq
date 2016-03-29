"""
CaseSearchES
------

.. code-block:: python

from corehq.apps.es import case_search as case_search_es

    q = (case_search_es.CaseSearchES()
         .domain('testproject'))
"""
from . import filters, queries

from corehq.apps.es.cases import CaseES
from corehq.pillows.const import CASE_SEARCH_ALIAS


PATH = "case_properties"


class CaseSearchES(CaseES):
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

    def case_property_query(self, key, value, clause=queries.SHOULD):
        """
        Search for a case property.
        Usage: (CaseSearchES()
                .domain('swashbucklers')
                .case_property_query("name", "redbeard", "must")
                .case_property_query("age", "15", "must")
                .case_property_query("has_parrot", "yes", "should")
                .case_property_query("is_pirate", "yes", "must_not"))

        Can be chained with regular filters . Running a set_query after this will destroy it.
        Clauses can be any of SHOULD, MUST, or MUST_NOT
        """

        # Filter by case_properties.key and do a text search in case_properties.value
        new_query = queries.nested(
            PATH,
            queries.filtered(
                queries.search_string_query(value, default_fields=["{}.value".format(PATH)]),
                filters.term("{}.key".format(PATH), key)
            )
        )
        current_query = self._query.get(queries.BOOL)
        if current_query is None:
            return self.set_query(
                queries.BOOL_CLAUSE(
                    queries.CLAUSES[clause]([new_query])
                )
            )
        elif current_query.get(clause) and isinstance(current_query[clause], list):
            current_query[clause] += [new_query]
        else:
            current_query.update(
                queries.CLAUSES[clause]([new_query])
            )
        return self


def case_property_filter(key, value):
    return filters.nested(
        PATH,
        filters.AND(
            filters.term("{}.key".format(PATH), key),
            filters.term("{}.value".format(PATH), value),
        )
    )
