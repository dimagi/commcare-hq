import uuid

from datetime import date
from django.test.testcases import SimpleTestCase
from django.test import TestCase
from mock import MagicMock, patch
from nose.plugins.attrib import attr

from corehq.apps.case_search.const import RELEVANCE_SCORE
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.apps.es.case_search import (
    case_property_missing,
    case_property_text_query
)
from corehq.elastic import get_es_new, SIZE_LIMIT
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import CaseSearchReindexerFactory
from corehq.pillows.mappings.case_search_mapping import (
    CASE_SEARCH_INDEX,
    CASE_SEARCH_INDEX_INFO,
)
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import create_and_save_a_case
from pillowtop.es_utils import initialize_index_and_mapping


@attr(es_test=True)
class TestCaseSearchES(ElasticTestMixin, SimpleTestCase):

    def setUp(self):
        self.es = CaseSearchES()

    def is_es7(self):
        return settings.ELASTICSEARCH_MAJOR_VERSION == 7

    def test_simple_case_property_query(self):
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "domain.exact": "swashbucklers"
                                }
                            },
                            {
                                "match_all": {}
                            }
                        ],
                        "must": {
                            "bool": {
                                "must": [
                                    {
                                        "nested": {
                                            "path": "case_properties",
                                            "query": {
                                                "bool": {
                                                    "filter": [
                                                        {
                                                            "bool": {
                                                                "filter": [
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
                                                                ]
                                                            }
                                                        }
                                                    ],
                                                    "must": {
                                                        "match_all": {}
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
        else:
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

        self.checkQuery(query, json_output, validate_query=False)

    def test_multiple_case_search_queries(self):
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "domain.exact": "swashbucklers"
                                }
                            },
                            {
                                "match_all": {}
                            }
                        ],
                        "must": {
                            "bool": {
                                "must": [
                                    {
                                        "nested": {
                                            "path": "case_properties",
                                            "query": {
                                                "bool": {
                                                    "filter": [
                                                        {
                                                            "bool": {
                                                                "filter": [
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
                                                                ]
                                                            }
                                                        }
                                                    ],
                                                    "must": {
                                                        "match_all": {}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                ],
                                "should": [
                                    {
                                        "bool": {
                                            "filter": [
                                                {
                                                    "nested": {
                                                        "path": "case_properties",
                                                        "query": {
                                                            "bool": {
                                                                "filter": [
                                                                    {
                                                                        "term": {
                                                                            "case_properties.key.exact": "parrot_name"
                                                                        }
                                                                    }
                                                                ],
                                                                "must": {
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
                                    },
                                    {
                                        "bool": {
                                            "filter": [
                                                {
                                                    "nested": {
                                                        "path": "case_properties",
                                                        "query": {
                                                            "bool": {
                                                                "filter": [
                                                                    {
                                                                        "term": {
                                                                            "case_properties.key.exact": "parrot_name"
                                                                        }
                                                                    }
                                                                ],
                                                                "must": {
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
                                ]
                            }
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
        self.checkQuery(query, json_output, validate_query=False)

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
        if self.is_es7():
            expected = {'query': {'bool': {'filter': [{'term': {'domain.exact': 'swashbucklers'}},
                               {'bool': {'must_not': {'term': {'owner_id': '123'}}}},
                               {'term': {'owner_id': '234'}},
                               {'match_all': {}}],
                    'must': {'match_all': {}}}},
                    'size': SIZE_LIMIT}
        else:
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
        self.checkQuery(query, expected, validate_query=False)


@attr(es_test=True)
class TestCaseSearchLookups(TestCase):

    def setUp(self):
        self.domain = 'case_search_es'
        super(TestCaseSearchLookups, self).setUp()
        FormProcessorTestUtils.delete_all_cases()
        self.elasticsearch = get_es_new()
        ensure_index_deleted(CASE_SEARCH_INDEX)

        # Bootstrap ES
        initialize_index_and_mapping(get_es_new(), CASE_SEARCH_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(CASE_SEARCH_INDEX)
        super(TestCaseSearchLookups, self).tearDown()

    def _make_case(self, domain, case_properties):
        # make a case
        case_properties = case_properties or {}
        case_id = case_properties.pop('_id')
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        owner_id = case_properties.pop('owner_id', None)
        case = create_and_save_a_case(domain, case_id, case_name, case_properties, owner_id=owner_id)
        return case

    def _bootstrap_cases_in_es_for_domain(self, domain):
        with patch('corehq.pillows.case_search.domains_needing_search_index',
                   MagicMock(return_value=[domain])):
            CaseSearchReindexerFactory(domain=domain).build().reindex()

    def _assert_query_runs_correctly(self, domain, input_cases, query, output):
        for case in input_cases:
            self._make_case(domain, case)
        self._bootstrap_cases_in_es_for_domain(domain)
        self.elasticsearch.indices.refresh(CASE_SEARCH_INDEX)
        self.assertItemsEqual(
            query.get_ids(),
            output
        )

    def test_simple_case_property_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'name': 'redbeard'},
                {'_id': 'c2', 'name': 'blackbeard'},
            ],
            CaseSearchES().domain(self.domain).case_property_query("name", "redbeard"),
            ['c1']
        )

    def test_multiple_case_search_queries(self):
        query = (CaseSearchES().domain(self.domain)
                 .case_property_query("name", "redbeard")
                 .case_property_query("parrot_name", "polly"))
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'name': 'redbeard', 'parrot_name': 'polly'},
                {'_id': 'c2', 'name': 'blackbeard', 'parrot_name': 'polly'},
                {'_id': 'c3', 'name': 'redbeard', 'parrot_name': 'molly'}
            ],
            query,
            ['c1']
        )

    def test_multiple_case_search_queries_should_clause(self):
        query = (CaseSearchES().domain(self.domain)
                 .case_property_query("name", "redbeard")
                 .case_property_query("parrot_name", "polly", clause="should"))
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'name': 'redbeard', 'parrot_name': 'polly'},
                {'_id': 'c2', 'name': 'blackbeard', 'parrot_name': 'polly'},
                {'_id': 'c3', 'name': 'redbeard', 'parrot_name': 'molly'}
            ],
            query,
            ['c1', 'c3']
        )

    def test_blacklisted_owner_ids(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'owner_id': '123'},
                {'_id': 'c2', 'owner_id': '234'},
            ],
            CaseSearchES().domain(self.domain).blacklist_owner_id('123'),
            ['c2']
        )

    def test_missing_case_property(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c2', 'name': 'blackbeard'},
                {'_id': 'c3', 'name': ''},
                {'_id': 'c4'},
            ],
            CaseSearchES().domain(self.domain).filter(case_property_missing('name')),
            ['c3'] # todo; flag farid
        )

    def test_full_text_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'description': 'redbeards are red'},
                {'_id': 'c2', 'description': 'blackbeards are black'},
            ],
            CaseSearchES().domain(self.domain).filter(case_property_text_query('description', 'red')),
            ['c1']
        )

    def test_numeric_range_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'num': '1'},
                {'_id': 'c2', 'num': '2'},
                {'_id': 'c3', 'num': '3'},
                {'_id': 'c4', 'num': '4'},
            ],
            CaseSearchES().domain(self.domain).numeric_range_case_property_query('num', gte=2, lte=3),
            ['c2', 'c3']
        )

    def test_date_range_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'dob': date(2020, 3, 1)},
                {'_id': 'c2', 'dob': date(2020, 3, 2)},
                {'_id': 'c3', 'dob': date(2020, 3, 3)},
                {'_id': 'c4', 'dob': date(2020, 3, 4)},
            ],
            CaseSearchES().domain(self.domain).date_range_case_property_query('dob', gte='2020-03-02', lte='2020-03-03'),
            ['c2', 'c3']
        )