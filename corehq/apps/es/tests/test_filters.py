from datetime import date

from django.test import SimpleTestCase

from corehq.apps.es import filters
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.forms import FormES
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.elastic import SIZE_LIMIT
from corehq.elastic import get_es_new
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping
from corehq.elastic import send_to_elasticsearch


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


class TestFiltersRun(SimpleTestCase):
    def setUp(self):
        self.es = get_es_new()
        self.index = XFORM_INDEX_INFO.index

    def tearDown(self):
        ensure_index_deleted(self.index)

    def _setup_data(self):
        initialize_index_and_mapping(self.es, XFORM_INDEX_INFO)
        doc1 = {'_id': 'doc1', 'domain': 'd', 'app_id': 'a'}
        doc2 = {'_id': 'doc2', 'domain': 'd', 'app_id': 'not_a'}
        doc3 = {'_id': 'doc3', 'domain': 'not_d', 'app_id': 'not_a'}
        for doc in [doc1, doc2, doc3]:
            send_to_elasticsearch('forms', doc)
        self.es.indices.refresh(self.index)

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
