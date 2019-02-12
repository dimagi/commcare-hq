from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy
from unittest import TestCase
from mock import patch

from corehq.apps.es import filters
from corehq.apps.es import forms, users
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestESQuery(ElasticTestMixin, TestCase):
    maxDiff = 1000

    def _check_user_location_query(self, query, with_ids):
        json_output = {
            'query': {
                'filtered': {
                    'filter': {
                        'and': [
                            {'or': (
                                {'and': (
                                    {'term': {'doc_type': 'CommCareUser'}},
                                    {'terms': {'assigned_location_ids': with_ids}}
                                )
                                },
                                {'and': (
                                    {'term': {'doc_type': 'WebUser'}},
                                    {'terms': {'domain_memberships.assigned_location_ids': with_ids}}
                                )
                                }
                            )}, {'term': {'is_active': True}},
                            {'term': {'base_doc': 'couchuser'}}
                        ]
                    },
                    'query': {'match_all': {}}}},
            'size': 1000000
        }
        raw_query = query.raw_query
        self.assertItemsEqual(
            raw_query['query']['filtered']['filter'].pop('and'),
            json_output['query']['filtered']['filter'].pop('and')
        )
        self.checkQuery(raw_query, json_output, is_raw_query=True)

    def test_basic_query(self):
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
            "size": SIZE_LIMIT
        }
        self.checkQuery(HQESQuery('forms'), json_output)

    def test_query_size(self):
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
            "size": 0
        }
        # use `is not None`; 0 or 1000000 == 1000000
        self.checkQuery(HQESQuery('forms').size(0), json_output)
        json_output['size'] = 123
        self.checkQuery(HQESQuery('forms').size(123), json_output)

    def test_form_query(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"not": {"missing": {
                                "field": "domain"}}},
                            {"term": {"doc_type": "xforminstance"}},
                            {"not": {"missing":
                                {"field": "xmlns"}}},
                            {"not": {"missing":
                                {"field": "form.meta.userID"}}},
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "size": SIZE_LIMIT
        }
        query = forms.FormES()
        raw_query = query.raw_query
        self.assertItemsEqual(
            raw_query['query']['filtered']['filter'].pop('and'),
            json_output['query']['filtered']['filter'].pop('and')
        )
        self.checkQuery(raw_query, json_output, is_raw_query=True)

    def test_user_query(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"is_active": True}},
                            {"term": {"base_doc": "couchuser"}},
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "size": SIZE_LIMIT
        }
        query = users.UserES()
        raw_query = query.raw_query
        self.assertItemsEqual(
            raw_query['query']['filtered']['filter'].pop('and'),
            json_output['query']['filtered']['filter'].pop('and')
        )
        self.checkQuery(raw_query, json_output, is_raw_query=True)

    def test_filtered_forms(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": "zombocom"}},
                            {"term": {"xmlns.exact": "banana"}},
                            {"not": {"missing": {
                                "field": "domain"}}},
                            {"term": {"doc_type": "xforminstance"}},
                            {"not": {"missing":
                                {"field": "xmlns"}}},
                            {"not": {"missing":
                                {"field": "form.meta.userID"}}},
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "size": SIZE_LIMIT
        }
        query = forms.FormES()\
                .filter(filters.domain("zombocom"))\
                .xmlns('banana')
        raw_query = query.raw_query
        self.assertItemsEqual(
            raw_query['query']['filtered']['filter'].pop('and'),
            json_output['query']['filtered']['filter'].pop('and')
        )
        self.checkQuery(raw_query, json_output, is_raw_query=True)

    def test_users_at_locations(self):
        location_ids = ['09d1a58cb849e53bb3a456a5957d998a', '09d1a58cb849e53bb3a456a5957d99ba']
        query = users.UserES().location(location_ids)
        self._check_user_location_query(query, location_ids)

    def test_remove_all_defaults(self):
        # Elasticsearch fails if you pass it an empty list of filters
        query = (users.UserES()
                 .remove_default_filter('not_deleted')
                 .remove_default_filter('active'))
        filters = query.raw_query['query']['filtered']['filter']['and']
        self.assertTrue(len(filters) > 0)

    def test_values_list(self):
        example_response = {
            '_shards': {'failed': 0, 'successful': 5, 'total': 5},
            'hits': {'hits': [{
                '_id': '8063dff5-460b-46f2-b4d0-5871abfd97d4',
                '_index': 'xforms_1cce1f049a1b4d864c9c25dc42648a45',
                '_score': 1.0,
                '_type': 'xform',
                '_source': {
                    'app_id': 'fe8481a39c3738749e6a4766fca99efd',
                    'doc_type': 'xforminstance',
                    'domain': 'mikesproject',
                    'xmlns': 'http://openrosa.org/formdesigner/3a7cc07c-551c-4651-ab1a-d60be3017485'
                    }
                },
                {
                    '_id': 'dc1376cd-0869-4c13-a267-365dfc2fa754',
                    '_index': 'xforms_1cce1f049a1b4d864c9c25dc42648a45',
                    '_score': 1.0,
                    '_type': 'xform',
                    '_source': {
                        'app_id': '3d622620ca00d7709625220751a7b1f9',
                        'doc_type': 'xforminstance',
                        'domain': 'jacksproject',
                        'xmlns': 'http://openrosa.org/formdesigner/54db1962-b938-4e2b-b00e-08414163ead4'
                        }
                    }
                ],
                'max_score': 1.0,
                'total': 5247
                },
            'timed_out': False,
            'took': 4
        }
        fields = ['app_id', 'doc_type', 'domain']
        query = forms.FormES()
        with patch('corehq.apps.es.es_query.run_query', return_value=example_response):
            response = query.values_list(*fields)
            self.assertEqual(
                [
                    ('fe8481a39c3738749e6a4766fca99efd', 'xforminstance', 'mikesproject'),
                    ('3d622620ca00d7709625220751a7b1f9', 'xforminstance', 'jacksproject')
                ],
                response
            )

            response = query.values_list('domain', flat=True)
            self.assertEqual(['mikesproject', 'jacksproject'], response)

    def test_sort(self):
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
            "size": SIZE_LIMIT,
            "sort": [{
                "timeEnd": {
                    "order": "asc"
                }
            }],
        }
        query = (
            HQESQuery('forms')
            .sort('timeEnd')
        )
        self.checkQuery(query, json_output)
        json_output['sort'] = [
            {"timeStart": {"order": "asc"}},
        ]
        self.checkQuery(query.sort('timeStart'), json_output)
        json_output['sort'] = [
            {"timeEnd": {"order": "asc"}},
            {"timeStart": {"order": "asc"}},
        ]
        self.checkQuery(query.sort('timeStart', reset_sort=False), json_output)

    def test_cleanup_before_run(self):
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
        expected_output = deepcopy(json_output)
        expected_output['size'] = 0
        query = HQESQuery('forms').date_histogram('by_day', 'date', 'day', '-01:00')
        self.checkQuery(query, json_output)
        self.checkQuery(query._clean_before_run(), expected_output)

    def test_exclude_source(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                "term": {
                                    "domain.exact": "test-exclude"
                                }
                            },
                            {
                                "match_all": {}
                            }
                        ]
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            },
            "_source": False,
            "size": SIZE_LIMIT,
        }
        query = HQESQuery('forms').domain('test-exclude').exclude_source()
        self.checkQuery(query, json_output)
