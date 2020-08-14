from datetime import date

from django.test import SimpleTestCase

from corehq.apps.es import filters
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.elastic import SIZE_LIMIT


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
