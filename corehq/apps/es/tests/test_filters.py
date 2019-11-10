from datetime import date

from django.test import SimpleTestCase

from corehq.apps.es import filters
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestFilters(ElasticTestMixin, SimpleTestCase):

    def test_nested_filter(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"nested": {
                                "path": "actions",
                                "filter": {
                                    "range": {
                                        "actions.date": {
                                            "gte": "2015-01-01",
                                            "lt": "2015-02-01"
                                        }
                                    }
                                }
                            }},
                            {"match_all": {}}
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "size": SIZE_LIMIT
        }

        start, end = date(2015, 1, 1), date(2015, 2, 1)
        query = (HQESQuery('cases')
                 .nested("actions",
                         filters.date_range("actions.date", gte=start, lt=end)))

        self.checkQuery(query, json_output)

    def test_not_term_filter(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                "not": {
                                    "term": {
                                        "type": "badcasetype"
                                    }
                                }
                            },
                            {"match_all": {}}
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "size": SIZE_LIMIT
        }

        query = HQESQuery('cases').filter(filters.not_term('type', 'badcasetype'))

        self.checkQuery(query, json_output)

    def test_not_or_rewrite(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                'and': [
                                    {
                                        "not": {
                                            "term": {
                                                "type": "A"
                                            }
                                        }
                                    },
                                    {
                                        "not": {
                                            "term": {
                                                "type": "B"
                                            }
                                        }
                                    },
                                ]
                            },
                            {"match_all": {}}
                        ]
                    },
                    "query": {"match_all": {}}
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


class TestSourceFiltering(ElasticTestMixin, SimpleTestCase):

    def test_source_include(self):
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
            "_source": "source_obj"
        }
        q = HQESQuery('forms').source('source_obj')
        self.checkQuery(q, json_output)
