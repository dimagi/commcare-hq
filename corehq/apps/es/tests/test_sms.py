from django.conf import settings
from django.test.testcases import SimpleTestCase
from nose.plugins.attrib import attr

from corehq.apps.es.sms import SMSES
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


@attr(es_test=True)
class TestSMSES(ElasticTestMixin, SimpleTestCase):
    def test_processed_or_incoming(self):
        if settings.ELASTICSEARCH_MAJOR_VERSION == 7:
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
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"term": {"domain.exact": "demo"}},
                                {
                                    "or": (
                                        {
                                            "not": {"term": {"direction": "o"}},
                                        },
                                        {
                                            "not": {"term": {"processed": False}},
                                        }
                                    ),
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
