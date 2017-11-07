from __future__ import absolute_import
from unittest import TestCase

from corehq.apps.es.case_search import CaseSearchES, flatten_result, RELEVANCE_SCORE
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestCaseSearchES(ElasticTestMixin, TestCase):

    def setUp(self):
        self.es = CaseSearchES()

    def test_simple_case_property_query(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                "term": {
                                    "domain.exact": "swashbucklers"
                                }
                            },
                            {
                                "match_all": {}
                            }
                        ]
                    },
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "filtered": {
                                                "filter": {
                                                    "term": {
                                                        "case_properties.key": "name"
                                                    }
                                                },
                                                "query": {
                                                    "match": {
                                                        "case_properties.value": {
                                                            "query": "redbeard",
                                                            "fuzziness": "0"
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "size": SIZE_LIMIT
        }

        query = self.es.domain('swashbucklers').case_property_query("name", "redbeard")

        self.checkQuery(query, json_output)

    def test_multiple_case_search_queries(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                "term": {
                                    "domain.exact": "swashbucklers"
                                }
                            },
                            {
                                "match_all": {}
                            }
                        ]
                    },
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "filtered": {
                                                "filter": {
                                                    "term": {
                                                        "case_properties.key": "name"
                                                    }
                                                },
                                                "query": {
                                                    "match": {
                                                        "case_properties.value": {
                                                            "query": "redbeard",
                                                            "fuzziness": "0"
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "filtered": {
                                                "filter": {
                                                    "term": {
                                                        "case_properties.key": "parrot_name"
                                                    }
                                                },
                                                "query": {
                                                    "match": {
                                                        "case_properties.value": {
                                                            "query": "polly",
                                                            "fuzziness": "AUTO"
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            ],
                            "should": [
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "filtered": {
                                                "filter": {
                                                    "term": {
                                                        "case_properties.key": "parrot_name"
                                                    }
                                                },
                                                "query": {
                                                    "match": {
                                                        "case_properties.value": {
                                                            "query": "polly",
                                                            "fuzziness": "0"
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "size": SIZE_LIMIT
        }

        query = (self.es.domain('swashbucklers')
                 .case_property_query("name", "redbeard")
                 .case_property_query("parrot_name", "polly", clause="should", fuzzy=True))
        self.checkQuery(query, json_output)

    def test_flatten_result(self):
        expected = {'name': 'blah', 'foo': 'bar', 'baz': 'buzz', RELEVANCE_SCORE: "1.095"}
        self.assertEqual(
            flatten_result(
                {
                    "_score": "1.095",
                    "_source": {
                        'name': 'blah',
                        'case_properties': [
                            {'key': 'foo', 'value': 'bar'},
                            {'key': 'baz', 'value': 'buzz'}]
                    }
                }
            ),
            expected
        )

    def test_blacklisted_owner_ids(self):
        query = self.es.domain('swashbucklers').blacklist_owner_id('123').owner('234')
        expected = {'query':
                    {'filtered':
                     {'filter':
                      {'and': [
                          {'term': {'domain.exact': 'swashbucklers'}},
                          {'not': {'term': {'owner_id': '123'}}},
                          {'term': {'owner_id': '234'}},
                          {'match_all': {}}
                      ]},
                      "query": {
                          "match_all": {}
                      }}},
                    'size': SIZE_LIMIT}
        self.checkQuery(query, expected)
