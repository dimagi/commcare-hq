from django.test.testcases import SimpleTestCase

from corehq.apps.es.sms import SMSES
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.elastic import SIZE_LIMIT


@es_test
class TestSMSES(ElasticTestMixin, SimpleTestCase):
    def test_processed_or_incoming(self):
        json_output = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "domain.exact": "demo"
                            }
                        },
                        {
                            "bool": {
                                "must_not": {
                                    "bool": {
                                        "filter": [
                                            {
                                                "term": {
                                                    "direction": "o"
                                                }
                                            },
                                            {
                                                "term": {
                                                    "processed": False
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

        query = SMSES().domain('demo').processed_or_incoming_messages()

        self.checkQuery(query, json_output)
