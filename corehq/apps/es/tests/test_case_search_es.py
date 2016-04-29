from unittest import TestCase

from corehq.apps.es.case_search import CaseSearchES, flatten_result
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
                                                            "fuzziness": "AUTO"
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
        expected = {'name': 'blah', 'foo': 'bar', 'baz': 'buzz'}
        self.assertEqual(
            flatten_result(
                {
                    'name': 'blah',
                    'case_properties': [
                        {'key': 'foo', 'value': 'bar'},
                        {'key': 'baz', 'value': 'buzz'}]
                }
            ),
            expected
        )
