from __future__ import absolute_import
from django.test.testcases import SimpleTestCase

from corehq.apps.es.sms import SMSES
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestSMSES(ElasticTestMixin, SimpleTestCase):
    def test_processed_or_incoming(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": "demo"}},
                            {
                                "not": {
                                    "and": (
                                        {"term": {"direction": "o"}},
                                        {"term": {"processed": False}},
                                    )
                                }
                            },
                            {"match_all": {}},
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "size": SIZE_LIMIT
        }

        query = SMSES().domain('demo').processed_or_incoming_messages()

        self.checkQuery(query, json_output)
