from unittest import TestCase

from corehq.apps.es.es_query import HQESQuery, ESQuerySet
from corehq.apps.es.tests import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestESFacet(ElasticTestMixin, TestCase):
    def test_terms_facet(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"match_all": {}}
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "facets": {
                "babies_saved": {
                    "terms": {
                        "field": "babies.count",
                        "size": 10,
                        "shard_size": SIZE_LIMIT,
                    }
                }
            },
            "size": SIZE_LIMIT,
        }
        query = HQESQuery('forms')\
                .terms_facet('babies.count', 'babies_saved', size=10)
        self.checkQuery(query, json_output)

    def test_facet_response(self):
        example_response = {
            "hits": {},
            "shards": {},
            "facets": {
                "user": {
                    "_type": "terms",
                    "missing": 0,
                    "total": 3406,
                    "other": 619,
                    "terms": [
                        {
                        "term": "92647b9eafd9ea5ace2d1470114dbddd",
                        "count": 579
                        },
                        {
                        "term": "df5123010b24fc35260a84547148de93",
                        "count": 310
                        },
                        {
                        "term": "df5123010b24fc35260a84547148d47e",
                        "count": 303
                        },
                        {
                        "term": "7334d1ab1cd8847c69fba75043ed43d3",
                        "count": 298
                        }
                    ]
                }
            }
        }
        expected_output = {
            "92647b9eafd9ea5ace2d1470114dbddd": 579,
            "df5123010b24fc35260a84547148de93": 310,
            "df5123010b24fc35260a84547148d47e": 303,
            "7334d1ab1cd8847c69fba75043ed43d3": 298,
        }
        query = HQESQuery('forms')\
                .terms_facet('form.meta.userID', 'user', size=10)
        res = ESQuerySet(example_response, query)
        output = res.facets.user.counts_by_term()
        self.assertEqual(output, expected_output)

    def test_bad_facet_name(self):
        with self.assertRaises(AssertionError):
            HQESQuery('forms')\
                .terms_facet('form.meta.userID', 'form.meta.userID', size=10)
