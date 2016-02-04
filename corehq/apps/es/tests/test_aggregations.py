from copy import deepcopy

from django.test.testcases import SimpleTestCase

from corehq.apps.es import filters
from corehq.apps.es.aggregations import TermsAggregation, FilterAggregation, FiltersAggregation, RangeAggregation, \
    AggregationRange
from corehq.apps.es.es_query import HQESQuery, ESQuerySet
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestAggregations(ElasticTestMixin, SimpleTestCase):

    def test_bad_aggregation_name(self):
        with self.assertRaises(AssertionError):
            HQESQuery('forms')\
                .terms_aggregation('form.meta.userID', 'form.meta.userID')

    def test_nested_aggregation(self):
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
            "aggs": {
                "users": {
                    "terms": {"field": "user_id"},
                    "aggs": {
                        "closed": {
                            "filter": {
                                "term": {"closed": True}
                            }
                        }
                    }
                },
                "total_by_status": {
                    "filters": {
                        "filters": {
                            "closed": {"term": {"closed": True}},
                            "open": {"term": {"closed": False}}
                        }
                    }
                }
            },
            "size": SIZE_LIMIT
        }

        query = HQESQuery('cases').aggregations([
            TermsAggregation("users", 'user_id').aggregation(
                FilterAggregation('closed', filters.term('closed', True))
            ),
            FiltersAggregation('total_by_status')
                .add_filter('closed', filters.term('closed', True))
                .add_filter('open', filters.term('closed', False))
        ])
        self.checkQuery(query, json_output)

    def test_result_parsing_basic(self):
        query = HQESQuery('cases').aggregations([
            FilterAggregation('closed', filters.term('closed', True)),
            FilterAggregation('open', filters.term('closed', False))
        ])

        raw_result = {
            "aggregations": {
                "closed": {
                    "doc_count": 1
                },
                "open": {
                    "doc_count": 2
                }
            }
        }
        queryset = ESQuerySet(raw_result, deepcopy(query))
        self.assertEqual(queryset.aggregations.closed.doc_count, 1)
        self.assertEqual(queryset.aggregations.open.doc_count, 2)

    def test_result_parsing_complex(self):
        query = HQESQuery('cases').aggregation(
            TermsAggregation("users", 'user_id').aggregation(
                FilterAggregation('closed', filters.term('closed', True))
            ).aggregation(
                FilterAggregation('open', filters.term('closed', False))
            )
        ).aggregation(
            RangeAggregation('by_date', 'name', [
                AggregationRange(end='c'),
                AggregationRange(start='f'),
                AggregationRange(start='k', end='p')
            ])
        )

        raw_result = {
            "aggregations": {
                "users": {
                    "buckets": [
                        {
                            "closed": {
                                "doc_count": 0
                            },
                            "doc_count": 2,
                            "key": "user1",
                            "open": {
                                "doc_count": 2
                            }
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0
                },
                "by_date": {
                    "buckets": {
                        "*-c": {
                            "to": "c",
                            "doc_count": 3
                        },
                        "f-*": {
                            "from": "f",
                            "doc_count": 8
                        },
                        "k-p": {
                            "from": "k",
                            "to": "p",
                            "doc_count": 6
                        }
                    }
                }
            },
        }
        queryset = ESQuerySet(raw_result, deepcopy(query))
        self.assertEqual(queryset.aggregations.users.buckets.user1.key, 'user1')
        self.assertEqual(queryset.aggregations.users.buckets.user1.doc_count, 2)
        self.assertEqual(queryset.aggregations.users.buckets.user1.closed.doc_count, 0)
        self.assertEqual(queryset.aggregations.users.buckets.user1.open.doc_count, 2)
        self.assertEqual(queryset.aggregations.users.buckets_dict['user1'].open.doc_count, 2)
        self.assertEqual(queryset.aggregations.users.counts_by_bucket, {
            'user1': 2
        })
        self.assertEqual(queryset.aggregations.by_date.counts_by_bucket, {
            '*-c': 3,
            'f-*': 8,
            'k-p': 6,
        })

    def test_range_aggregation(self):
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
            "aggs": {
                "by_date": {
                    "range": {
                        "field": "name",
                        "keyed": True,
                        "ranges": [
                            {"to": "c"},
                            {"from": "f"},
                            {"from": "k", "to": "p", "key": "k-p"},
                        ]
                    }
                },
            },
            "size": SIZE_LIMIT
        }
        query = HQESQuery('cases').aggregation(
            RangeAggregation('by_date', 'name', [
                AggregationRange(end='c'),
                AggregationRange(start='f'),
                AggregationRange(start='k', end='p', key='k-p')
            ])
        )

        self.checkQuery(query, json_output)

    def test_date_histogram(self):
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
            "aggs": {
                "by_day": {
                    "date_histogram": {
                        "field": "date",
                        "interval": "day",
                        "time_zone": "-01:00"
                    }
                }
            },
            "size": SIZE_LIMIT
        }
        query = HQESQuery('forms').date_histogram('by_day', 'date', 'day', '-01:00')
        self.checkQuery(query, json_output)

    def test_histogram_aggregation(self):
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
        expected_output = example_response['aggregations']['forms_by_date']['buckets']
        query = HQESQuery('forms').date_histogram('forms_by_date', '', '')
        res = ESQuerySet(example_response, query)
        output = res.aggregations.forms_by_date.raw_buckets
        self.assertEqual(output, expected_output)

