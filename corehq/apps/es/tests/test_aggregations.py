import uuid
from datetime import datetime

from django.test.testcases import SimpleTestCase

from corehq.apps.es import FormES, filters
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.aggregations import (
    AggregationRange,
    DateHistogram,
    ExtendedStatsAggregation,
    FilterAggregation,
    FiltersAggregation,
    GeohashGridAggregation,
    MissingAggregation,
    NestedAggregation,
    RangeAggregation,
    StatsAggregation,
    TermsAggregation,
    TopHitsAggregation,
)
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es.const import SIZE_LIMIT
from corehq.apps.es.es_query import ESQuerySet, HQESQuery
from corehq.apps.es.tests.utils import (
    ElasticTestMixin,
    es_test,
    populate_es_index,
)


@es_test
class TestAggregations(ElasticTestMixin, SimpleTestCase):

    def test_bad_aggregation_name(self):
        with self.assertRaises(AssertionError):
            HQESQuery('forms')\
                .terms_aggregation('form.meta.userID', 'form.meta.userID')

    def test_nesting_aggregations(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "users": {
                    "terms": {
                        "field": "user_id",
                        "size": SIZE_LIMIT
                    },
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
            "size": 0
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
        queryset = ESQuerySet(raw_result, query.clone())
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
        queryset = ESQuerySet(raw_result, query.clone())
        self.assertEqual(queryset.aggregations.users.buckets.user1.key, 'user1')
        self.assertEqual(queryset.aggregations.users.buckets.user1.doc_count, 2)
        self.assertEqual(queryset.aggregations.users.buckets.user1.closed.doc_count, 0)
        self.assertEqual(queryset.aggregations.users.buckets.user1.open.doc_count, 2)
        self.assertEqual(queryset.aggregations.users.buckets_dict['user1'].open.doc_count, 2)
        self.assertEqual(queryset.aggregations.users.counts_by_bucket(), {
            'user1': 2
        })
        self.assertEqual(queryset.aggregations.by_date.counts_by_bucket(), {
            '*-c': 3,
            'f-*': 8,
            'k-p': 6,
        })

    def test_range_aggregation(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
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
            "size": 0
        }
        query = HQESQuery('cases').aggregation(
            RangeAggregation('by_date', 'name', [
                AggregationRange(end='c'),
                AggregationRange(start='f'),
                AggregationRange(start='k', end='p', key='k-p')
            ])
        )

        self.checkQuery(query, json_output)

    def test_stats_aggregation(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "name_stats": {
                    "stats": {
                        "field": "name",
                        "script": "MY weird script"
                    }
                },
            },
            "size": 0
        }
        query = HQESQuery('cases').aggregation(
            StatsAggregation('name_stats', 'name', script='MY weird script')
        )
        self.checkQuery(query, json_output)

    def test_extended_stats_aggregation(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "name_stats": {
                    "extended_stats": {
                        "field": "name",
                        "script": "MY weird script"
                    }
                },
            },
            "size": 0
        }
        query = HQESQuery('cases').aggregation(
            ExtendedStatsAggregation('name_stats', 'name', script='MY weird script')
        )
        self.checkQuery(query, json_output)

    def test_top_hits_aggregation(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "name_top_hits": {
                    "top_hits": {
                        "sort": [{
                            "my_awesome_field": {
                                "order": "desc"
                            }
                        }],
                        "_source": {
                            "include": [
                                "title"
                            ]
                        },
                        "size": 2
                    },
                },
            },
            "size": 0
        }
        query = HQESQuery('cases').aggregation(
            TopHitsAggregation(
                'name_top_hits',
                field='my_awesome_field',
                is_ascending=False,
                size=2,
                include=['title'])
        )
        self.checkQuery(query, json_output)

    def test_missing_aggregation(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "missing_user_id": {
                    "missing": {
                        "field": "user_id"
                    }
                },
            },
            "size": 0
        }
        query = HQESQuery('cases').aggregation(
            MissingAggregation(
                'missing_user_id',
                'user_id',
            )
        )
        self.checkQuery(query, json_output)

    def test_date_histogram(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "by_day": {
                    "date_histogram": {
                        "field": "date",
                        "interval": "day",
                        "time_zone": "-01:00",
                        'format': 'yyyy-MM-dd',
                        'min_doc_count': 1,
                    }
                }
            },
            "size": 0
        }
        query = HQESQuery('forms').aggregation(
            DateHistogram('by_day', 'date', DateHistogram.Interval.DAY, '-01:00'))
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
                    }, {
                        "key": 1464284800000,
                        "doc_count": 3
                    }]
                }
            }
        }
        expected_output = example_response['aggregations']['forms_by_date']['buckets']
        query = HQESQuery('forms').aggregation(
            DateHistogram('forms_by_date', '', DateHistogram.Interval.DAY))
        res = ESQuerySet(example_response, query)
        output = res.aggregations.forms_by_date.raw_buckets
        self.assertEqual(output, expected_output)

    def test_nested_aggregation(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "case_actions": {
                    "nested": {
                        "path": "actions"
                    }
                },
            },
            "size": 0
        }
        query = HQESQuery('cases').aggregation(
            NestedAggregation(
                'case_actions',
                'actions',
            )
        )
        self.checkQuery(query, json_output)

    def test_terms_aggregation_with_order(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "aggs": {
                "name": {
                    "terms": {
                        "field": "name",
                        "size": 1000000,
                        "order": [{
                            "sort_field": "asc"
                        }]
                    },
                },
            },
            "size": 0
        }
        query = HQESQuery('cases').aggregation(
            TermsAggregation('name', 'name').order('sort_field')
        )
        self.checkQuery(query, json_output)

    def test_terms_aggregation_does_not_accept_zero_size(self):
        error_message = "Aggregation size must be greater than 0"
        with self.assertRaisesMessage(AssertionError, error_message):
            HQESQuery('cases').aggregation(
                TermsAggregation('name', 'name').order('sort_field').size(0)
            )
        with self.assertRaisesMessage(AssertionError, error_message):
            HQESQuery('cases').aggregation(
                TermsAggregation('name', 'name', 0).order('sort_field')
            )

    def test_geohash_grid_aggregation(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "domain.exact": "test-domain"
                            }
                        },
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "size": 0,
            "aggs": {
                "name": {
                    "geohash_grid": {
                        "field": "case_location",
                        "precision": 6
                    }
                }
            }
        }
        query = CaseSearchES().domain('test-domain').aggregation(
            GeohashGridAggregation('name', 'case_location', 6)
        )
        self.checkQuery(query, json_output)


@es_test(requires=[form_adapter], setup_class=True)
class TestDateHistogram(SimpleTestCase):
    domain = str(uuid.uuid4())

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        forms = [{
            '_id': str(uuid.uuid4()),
            'domain': cls.domain,
            'received_on': datetime.fromisoformat(d),
            'form': {},
        } for d in [
            '2021-12-09',
            '2022-01-01',
            '2022-01-18',
            '2022-02-23',
            '2022-03-01',
            '2022-03-05',
            '2022-03-13',
            '2022-03-13',
            '2022-03-16',
            '2022-04-25',
            '2022-05-04',
            '2022-05-04',
            '2022-05-09',
            '2022-05-10',
            '2022-05-20',
            '2022-05-27',
            '2022-06-07',
        ]]
        populate_es_index(forms, 'forms')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def _run_aggregation(self, aggregation):
        return (FormES()
                .remove_default_filters()
                .domain(self.domain)
                .aggregation(aggregation)
                .run())

    def test_year_histogram(self):
        res = self._run_aggregation(DateHistogram(
            'submissions', 'received_on', DateHistogram.Interval.YEAR))
        counts = res.aggregations.submissions.counts_by_bucket()
        self.assertEqual(16, counts['2022'])

    def test_month_histogram(self):
        res = self._run_aggregation(DateHistogram(
            'submissions', 'received_on', DateHistogram.Interval.MONTH))
        counts = res.aggregations.submissions.counts_by_bucket()
        self.assertEqual(5, counts['2022-03'])

    def test_day_histogram(self):
        res = self._run_aggregation(DateHistogram(
            'submissions', 'received_on', DateHistogram.Interval.DAY))
        counts = res.aggregations.submissions.counts_by_bucket()
        self.assertEqual(2, counts['2022-03-13'])

    def test_only_nonzero_buckets_returned(self):
        res = self._run_aggregation(DateHistogram(
            'submissions', 'received_on', DateHistogram.Interval.DAY))
        counts = res.aggregations.submissions.counts_by_bucket()
        self.assertEqual(15, len(counts))
