from datetime import date
from unittest import TestCase

from corehq.apps.es import filters
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.tests import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestFilters(ElasticTestMixin, TestCase):
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


class TestSourceFiltering(ElasticTestMixin, TestCase):
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
            "_source": ["source_obj"]
        }
        q = HQESQuery('forms').source('source_obj')
        self.checkQuery(q, json_output)
