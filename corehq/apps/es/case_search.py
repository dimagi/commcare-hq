"""
CaseSearchES
------

.. code-block:: python

from corehq.apps.es import case_search as case_search_es

    q = (case_search_es.CaseSearchES()
         .domain('testproject')
"""
from __future__ import absolute_import

from corehq.apps.es.aggregations import TermsAggregation, BucketResult
from corehq.apps.es.cases import CaseES, owner
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_ALIAS

from . import filters, queries

PATH = "case_properties"
RELEVANCE_SCORE = "commcare_search_score"


class CaseSearchES(CaseES):
    index = CASE_SEARCH_ALIAS

    @property
    def builtin_filters(self):
        return [case_property_filter, blacklist_owner_id] + super(CaseSearchES, self).builtin_filters

    @property
    def _case_property_queries(self):
        """
        Returns all current case_property queries
        """
        try:
            return self.es_query['query']['filtered']['query']['bool']['must']
        except (KeyError, TypeError):
            return []

    def case_property_query(self, key, value, clause=queries.MUST, fuzzy=False):
        """
        Search for a case property.
        Usage: (CaseSearchES()
                .domain('swashbucklers')
                .case_property_query("name", "rebdeard", "must", fuzzy=True)
                .case_property_query("age", "15", "must")
                .case_property_query("has_parrot", "yes", "should")
                .case_property_query("is_pirate", "yes", "must_not"))

        Can be chained with regular filters . Running a set_query after this will destroy it.
        Clauses can be any of SHOULD, MUST, or MUST_NOT
        """
        # Filter by case_properties.key and do a text search in case_properties.value
        result = self
        if fuzzy:
            # Results must at least match the fuzzy value, and exact matches are weighted higher. `clause` param
            # is overridden to do this.
            fuzzy_query = queries.nested(
                PATH,
                queries.filtered(
                    queries.match(value, '{}.value'.format(PATH), fuzziness='AUTO'),
                    filters.term('{}.key'.format(PATH), key),
                )
            )
            result = result._add_query(fuzzy_query, queries.MUST)
            clause = queries.SHOULD

        exact_query = queries.nested(
            PATH,
            queries.filtered(
                queries.match(value, '{}.value'.format(PATH), fuzziness='0'),
                filters.term('{}.key'.format(PATH), key),
            )
        )
        return result._add_query(exact_query, clause)

    def regexp_case_property_query(self, key, regex, clause=queries.MUST):
        new_query = queries.nested(
            PATH,
            queries.filtered(
                filters.term('{}.key'.format(PATH), key),
                queries.regexp('{}.value'.format(PATH), regex)
            )
        )
        return self._add_query(new_query, clause)

    def _add_query(self, new_query, clause):
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


def blacklist_owner_id(owner_id):
    return filters.NOT(owner(owner_id))


def flatten_result(hit):
    """Flattens a result from CaseSearchES into the format that Case serializers
    expect

    i.e. instead of {'name': 'blah', 'case_properties':{'key':'foo', 'value':'bar'}} we return
    {'name': 'blah', 'foo':'bar'}
    """
    result = hit['_source']
    result[RELEVANCE_SCORE] = hit['_score']
    case_properties = result.pop('case_properties', [])
    for case_property in case_properties:
        key = case_property.get('key')
        value = case_property.get('value')
        if key and value:
            result[key] = value
    return result


class CasePropertyAggregationResult(BucketResult):

    @property
    def raw_buckets(self):
        return self.result[self.aggregation.field]['values']['buckets']

    @property
    def buckets(self):
        """returns a list of buckets rather than a namedtuple since case property values can
        have non-valid python names
        """
        return self.bucket_list


class CasePropertyAggregation(TermsAggregation):
    type = "case_property"
    result_class = CasePropertyAggregationResult

    def __init__(self, name, field, size=None):
        self.name = name
        self.field = field
        self.body = {
            "nested": {
                "path": "case_properties"
            },
            "aggs": {
                field: {
                    "filter": {
                        "term": {
                            "case_properties.key": field,
                        }
                    },
                    "aggs": {
                        "values": {
                            "terms": {
                                "field": "case_properties.value"
                            }
                        }
                    }
                }
            }
        }
