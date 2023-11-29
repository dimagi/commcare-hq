from datetime import date

from django.test import SimpleTestCase

from corehq.apps.es import CaseSearchES, filters
from corehq.apps.es.const import SIZE_LIMIT
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.forms import FormES, form_adapter
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test


@es_test
class TestFilters(ElasticTestMixin, SimpleTestCase):

    def test_nested_filter(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "nested": {
                                "path": "actions",
                                "query": {
                                    "bool": {
                                        "filter": {
                                            "range": {
                                                "actions.date": {
                                                    "gte": "2015-01-01",
                                                    "lt": "2015-02-01"
                                                }
                                            }
                                        }
                                    }
                                }
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
            "size": SIZE_LIMIT
        }

        start, end = date(2015, 1, 1), date(2015, 2, 1)
        query = (HQESQuery('cases')
                 .nested("actions",
                         filters.date_range("actions.date", gte=start, lt=end)))

        self.checkQuery(query, json_output, validate_query=False)

    def test_not_term_filter(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "bool": {
                                "must_not": {
                                    "term": {
                                        "type": "badcasetype"
                                    }
                                }
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
            "size": SIZE_LIMIT
        }

        query = HQESQuery('cases').filter(filters.not_term('type', 'badcasetype'))

        self.checkQuery(query, json_output)

    def test_not_or_rewrite(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "bool": {
                                "must_not": {
                                    "bool": {
                                        "should": [
                                            {
                                                "term": {
                                                    "type": "A"
                                                }
                                            },
                                            {
                                                "term": {
                                                    "type": "B"
                                                }
                                            }
                                        ]
                                    }
                                }
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
            "size": SIZE_LIMIT
        }
        query = HQESQuery('cases').filter(
            filters.NOT(
                filters.OR(filters.term('type', 'A'), filters.term('type', 'B'))
            )
        )

        self.checkQuery(query, json_output)

    def test_not_and_rewrite(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "bool": {
                                "must_not": {
                                    "bool": {
                                        "filter": [
                                            {
                                                "term": {
                                                    "type": "A"
                                                }
                                            },
                                            {
                                                "term": {
                                                    "type": "B"
                                                }
                                            }
                                        ]
                                    }
                                }
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
            "size": SIZE_LIMIT
        }
        query = HQESQuery('cases').filter(
            filters.NOT(
                filters.AND(filters.term('type', 'A'), filters.term('type', 'B'))
            )
        )

        self.checkQuery(query, json_output)

    def test_geo_bounding_box(self):
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
                            "geo_bounding_box": {
                                "location": {
                                    "top_left": "40.73 -74.1",
                                    "bottom_right": "40.01 -71.12",
                                }
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
            "size": SIZE_LIMIT
        }
        query = CaseSearchES().domain('test-domain').filter(
            filters.geo_bounding_box('location', '40.73 -74.1', '40.01 -71.12')
        )
        self.checkQuery(
            query,
            json_output,
            validate_query=False,  # Avoid creating an index just for this test
        )

    def test_geo_shape(self):
        points_list = [
            {"lat": 40.73, "lon": -74.1},
            {"lat": 40.01, "lon": -71.12},
        ]

        query = CaseSearchES().filter(
            filters.geo_shape('case_gps', points_list)
        )
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "geo_shape": {
                                "case_gps": {
                                    "shape": [
                                        {
                                            "lat": 40.73,
                                            "lon": -74.1
                                        },
                                        {
                                            "lat": 40.01,
                                            "lon": -71.12
                                        }
                                    ],
                                    "relation": "intersects"
                                }
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
            "size": SIZE_LIMIT
        }
        self.checkQuery(
            query,
            json_output,
            validate_query=False,
        )

    def test_geo_grid(self):
        query = CaseSearchES().filter(
            filters.geo_grid('location', 'u0')
        )
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "geo_grid": {
                                "location": {
                                    "geohash": "u0"
                                }
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
            "size": SIZE_LIMIT
        }
        self.checkQuery(
            query,
            json_output,
            validate_query=False,
        )


@es_test
class TestSourceFiltering(ElasticTestMixin, SimpleTestCase):

    def test_source_include(self):
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
            "size": SIZE_LIMIT,
            "_source": "source_obj"
        }
        q = HQESQuery('forms').source('source_obj')
        self.checkQuery(q, json_output)


@es_test(requires=[form_adapter])
class TestFiltersRun(SimpleTestCase):

    def _setup_data(self):
        doc1 = {'_id': 'doc1', 'domain': 'd', 'app_id': 'a', 'form': {}}
        doc2 = {'_id': 'doc2', 'domain': 'd', 'app_id': 'not_a', 'form': {}}
        doc3 = {'_id': 'doc3', 'domain': 'not_d', 'app_id': 'not_a', 'form': {}}
        for doc in [doc1, doc2, doc3]:
            form_adapter.index(doc, refresh=True)

    def test_not_filter_edge_case(self):
        self._setup_data()
        query = FormES().remove_default_filters().filter(
            filters.NOT(filters.OR(
                filters.term('domain', 'd'),
                filters.term('app_id', 'a')
            ))
        )
        self.assertEqual(query.run().doc_ids, ['doc3'])

    def test_ids_query(self):
        self._setup_data()
        ids = ['doc1', 'doc2']
        self.assertEqual(
            FormES().remove_default_filters().ids_query(ids).exclude_source().run().doc_ids,
            ids
        )
