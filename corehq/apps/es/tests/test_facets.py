from unittest import TestCase
from unittest.case import skip

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

    @skip('deprecated')
    def test_date_histogram_facet(self):
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
                "forms_by_date": {
                    "date_histogram": {
                        "field": "received_on",
                        "interval": "month",
                        "time_zone": None
                    }
                }
            },
            "size": SIZE_LIMIT,
        }
        query = HQESQuery('forms')\
                .date_histogram('forms_by_date', 'received_on', 'month')
        self.checkQuery(query, json_output)

    def test_histogram_facet_response(self):
        example_response = {
            "hits": {},
            "shards": {},
            "facets": {
                "forms_by_date": {
                    "_type": "date_histogram",
                    "entries": [{
                        "time": 1454284800000,
                        "count": 8
                    },
                    {
                        "time": 1464284800000,
                        "count": 3
                    }]
                }
            }
        }
        expected_output = example_response['facets']['forms_by_date']['entries']
        query = HQESQuery('forms')
        res = ESQuerySet(example_response, query)
        output = res.facet('forms_by_date', 'entries')
        self.assertEqual(output, expected_output)

    def test_histogram_aggregation_as_facet_response(self):
        example_response = {
            "hits": {},
            "shards": {},
            "aggregations": {
                "forms_by_date": {
                    "buckets": [{
                        "key": 1454284800000,
                        "doc_count": 8
                    },
                    {
                        "key": 1464284800000,
                        "doc_count": 3
                    }]
                }
            }
        }
        expected_output = [{
                "time": 1454284800000,
                "count": 8
            },
            {
                "time": 1464284800000,
                "count": 3
        }]
        query = HQESQuery('forms').date_histogram('forms_by_date', '', '')
        res = ESQuerySet(example_response, query)
        output = res.aggregations.forms_by_date.as_facet_result()
        self.assertEqual(output, expected_output)
