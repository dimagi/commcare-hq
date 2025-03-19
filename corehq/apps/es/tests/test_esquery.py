from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.es import filters, forms, users
from corehq.apps.es.const import SCROLL_SIZE, SIZE_LIMIT
from corehq.apps.es.es_query import HQESQuery, InvalidQueryError
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test


@es_test(requires=[users.user_adapter])
class TestESQuery(ElasticTestMixin, SimpleTestCase):
    maxDiff = 1000

    def _check_user_location_query(self, query, with_ids):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "bool": {
                                "should": (
                                    {
                                        "bool": {
                                            "filter": (
                                                {"term": {"doc_type": "CommCareUser"}},
                                                {"terms": {"assigned_location_ids": with_ids}})}
                                    },
                                    {
                                        "bool": {
                                            "filter": (
                                                {"term": {"doc_type": "WebUser"}},
                                                {"terms": {"domain_memberships.assigned_location_ids": with_ids}})}
                                    }
                                )
                            }
                        },
                        {'term': {'base_doc': 'couchuser'}},
                        {'term': {'is_active': True}}
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "size": SIZE_LIMIT
        }
        raw_query = query.raw_query
        self.checkQuery(raw_query, json_output, is_raw_query=True)

    def test_basic_query(self):
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
            "size": SIZE_LIMIT
        }
        self.checkQuery(HQESQuery('forms'), json_output)

    def test_query_size(self):
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
            "size": 0
        }

        # use `is not None`; 0 or 1000000 == 1000000
        self.checkQuery(HQESQuery('forms').size(0), json_output)
        json_output['size'] = 123
        self.checkQuery(HQESQuery('forms').size(123), json_output)

    def test_form_query(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"doc_type": "xforminstance"}},
                        {"exists": {"field": "xmlns"}},
                        {"exists": {"field": "form.meta.userID"}},
                        {"exists": {"field": "domain"}},
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "size": SIZE_LIMIT
        }
        query = forms.FormES()
        raw_query = query.raw_query
        self.checkQuery(raw_query, json_output, is_raw_query=True)

    def test_user_query(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "base_doc": "couchuser"
                            }
                        },
                        {
                            "term": {
                                "is_active": True
                            }
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "size": SIZE_LIMIT
        }
        query = users.UserES()
        raw_query = query.raw_query
        self.checkQuery(raw_query, json_output, is_raw_query=True)

    def test_filtered_forms(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"domain.exact": "zombocom"}},
                        {"term": {"xmlns.exact": "banana"}},
                        {"term": {"doc_type": "xforminstance"}},
                        {"exists": {"field": "xmlns"}},
                        {"exists": {"field": "form.meta.userID"}},
                        {"exists": {"field": "domain"}},
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "size": SIZE_LIMIT
        }
        query = forms.FormES()\
            .filter(filters.domain("zombocom"))\
            .xmlns('banana')
        raw_query = query.raw_query
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
        filters = query.raw_query['query']['bool']['filter']
        self.assertTrue(len(filters) > 0)

    def test_values_list(self):
        example_response = {
            '_shards': {'failed': 0, 'successful': 5, 'total': 5},
            'hits': {
                'hits': [
                    {
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
        with patch.object(query.adapter, "search", return_value=example_response):
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
            "sort": [
                {
                    "timeEnd": {
                        "order": "asc"
                    }
                }
            ],
            "size": SIZE_LIMIT
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

    def test_sort_raises_on__id_field(self):
        with self.assertRaisesMessage(AssertionError, "Cannot sort on reserved _id field"):
            HQESQuery('forms').sort('_id')

    def test_exclude_source(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "domain.exact": "test-exclude"
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
            "_source": False,
            "size": SIZE_LIMIT,
        }
        query = HQESQuery('forms').domain('test-exclude').exclude_source()
        self.checkQuery(query, json_output)

    def test_scroll_uses_scroll_size_from_query(self):
        query = HQESQuery('forms').size(1)
        self.assertEqual(1, query._size)
        scroll_query_testfunc = self._scroll_query_mock_assert(size=1)
        with patch.object(query.adapter, "scroll", scroll_query_testfunc):
            list(query.scroll())

    def test_scroll_without_query_size_uses_default_scroll_size(self):
        query = HQESQuery('forms')
        self.assertIsNone(query._size)
        scroll_query_testfunc = self._scroll_query_mock_assert(size=SCROLL_SIZE)
        with patch.object(query.adapter, "scroll", scroll_query_testfunc):
            list(query.scroll())

    def test_scroll_ids_uses_scroll_size_from_query(self):
        query = HQESQuery('forms').size(1)
        self.assertEqual(1, query._size)
        scroll_query_testfunc = self._scroll_query_mock_assert(size=1)
        with patch.object(query.adapter, "scroll", scroll_query_testfunc):
            list(query.scroll_ids())

    def test_scroll_ids_without_query_size_uses_default_scroll_size(self):
        query = HQESQuery('forms')
        self.assertIsNone(query._size)
        scroll_query_testfunc = self._scroll_query_mock_assert(size=SCROLL_SIZE)
        with patch.object(query.adapter, "scroll", scroll_query_testfunc):
            list(query.scroll_ids())

    def test_scroll_with_aggregations_raises(self):
        query = HQESQuery('forms').terms_aggregation('domain.exact', 'domain')
        with self.assertRaises(InvalidQueryError):
            list(query.scroll())

    def _scroll_query_mock_assert(self, **raw_query_assertions):
        def scroll_query_tester(raw_query, **kw):
            for key, value in raw_query_assertions.items():
                self.assertEqual(value, raw_query[key])
            return []
        self.assertNotEqual({}, raw_query_assertions)
        return scroll_query_tester

    def test_scroll_ids_to_disk_and_iter_docs(self):
        doc = {"_id": "test", "doc_type": "SomeUser", "username": "u1"}
        with patch('corehq.apps.groups.dbaccessors.get_group_id_name_map_by_user', return_value=[]):
            users.user_adapter.index(doc, refresh=True)
        query = users.UserES().remove_default_filters()
        # add extra keys added in transformation
        doc.update({
            '_id': 'test',
            'doc_id': 'test',
            'base_username': 'u1',
            'user_data_es': [],
            '__group_ids': [],
            '__group_names': []
        })
        self.assertEqual([doc], list(query.scroll_ids_to_disk_and_iter_docs()))

    def test_scroll_ids_to_disk_and_iter_docs_does_not_raise_for_deleted_doc(self):

        def scroll_then_delete_one():
            results = real_scroll()
            users.user_adapter.delete(doc2["_id"], refresh=True)
            return results

        doc1 = {"_id": "test", "doc_type": "SomeUser", "username": "u1"}
        doc2 = {"_id": "vanishes", "doc_type": "SomeUser", "username": "u2"}
        for doc in [doc1, doc2]:
            with patch('corehq.apps.groups.dbaccessors.get_group_id_name_map_by_user', return_value=[]):
                users.user_adapter.index(doc, refresh=True)
        query = users.UserES().remove_default_filters()
        # add extra keys added in transformation
        doc1.update({
            'base_username': 'u1',
            'doc_id': 'test',
            'user_data_es': [],
            '__group_ids': [],
            '__group_names': []
        })
        real_scroll = query.scroll
        with patch.object(query, "scroll", scroll_then_delete_one):
            self.assertEqual([doc1], list(query.scroll_ids_to_disk_and_iter_docs()))
