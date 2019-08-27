from django.test.testcases import SimpleTestCase

from corehq.apps.case_search.const import RELEVANCE_SCORE
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.elastic import SIZE_LIMIT


class TestCaseSearchES(ElasticTestMixin, SimpleTestCase):

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
                                                "query": {
                                                    "match_all": {
                                                    }
                                                },
                                                "filter": {
                                                    "and": (
                                                        {
                                                            "term": {
                                                                "case_properties.key.exact": "name"
                                                            }
                                                        },
                                                        {
                                                            "term": {
                                                                "case_properties.value.exact": "redbeard"
                                                            }
                                                        }
                                                    )
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
                                                    "and": (
                                                        {
                                                            "term": {
                                                                "case_properties.key.exact": "name"
                                                            }
                                                        },
                                                        {
                                                            "term": {
                                                                "case_properties.value.exact": "redbeard"
                                                            }
                                                        }
                                                    )
                                                },
                                                "query": {
                                                    "match_all": {
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
                                                        "case_properties.key.exact": "parrot_name"
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
                                },
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "filtered": {
                                                "filter": {
                                                    "term": {
                                                        "case_properties.key.exact": "parrot_name"
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
                            {'key': '@case_id', 'value': 'should be removed'},
                            {'key': 'name', 'value': 'should be removed'},
                            {'key': 'case_name', 'value': 'should be removed'},
                            {'key': 'last_modified', 'value': 'should be removed'},
                            {'key': 'foo', 'value': 'bar'},
                            {'key': 'baz', 'value': 'buzz'}]
                    }
                },
                include_score=True
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
