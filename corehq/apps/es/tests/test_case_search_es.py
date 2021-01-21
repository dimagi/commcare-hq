import uuid

from datetime import date
from django.test.testcases import SimpleTestCase
from django.test import TestCase
from mock import MagicMock, patch

from corehq.apps.case_search.const import RELEVANCE_SCORE
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.case_search.models import CaseSearchConfig, FuzzyProperties
from corehq.apps.case_search.utils import CaseSearchCriteria
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
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
from corehq.util.test_utils import create_and_save_a_case, flag_enabled
from pillowtop.es_utils import initialize_index_and_mapping


@es_test
class TestCaseSearchES(ElasticTestMixin, SimpleTestCase):

    def setUp(self):
        self.es = CaseSearchES()

    def test_simple_case_property_query(self):
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

        query = self.es.domain('swashbucklers').case_property_query("name", "redbeard")

        self.checkQuery(query, json_output, validate_query=False)

    def test_multiple_case_search_queries(self):
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
                                },
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
        expected = {'query': {'bool': {'filter': [{'term': {'domain.exact': 'swashbucklers'}},
                            {'bool': {'must_not': {'term': {'owner_id': '123'}}}},
                            {'term': {'owner_id': '234'}},
                            {'match_all': {}}],
                'must': {'match_all': {}}}},
                'size': SIZE_LIMIT}

        self.checkQuery(query, expected, validate_query=False)


@es_test
class TestCaseSearchLookups(TestCase):

    def setUp(self):
        self.domain = 'case_search_es'
        self.case_type = 'person'
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
        case = create_and_save_a_case(
            domain, case_id, case_name, case_properties, owner_id=owner_id, case_type=self.case_type)
        return case

    def _bootstrap_cases_in_es_for_domain(self, domain):
        with patch('corehq.pillows.case_search.domains_needing_search_index',
                   MagicMock(return_value=[domain])):
            CaseSearchReindexerFactory(domain=domain).build().reindex()

    def _assert_query_runs_correctly(self, domain, input_cases, query, xpath_query, output):
        self._assert_queries_run_correctly(domain, input_cases, xpath_query, [(query, output)])

    def _assert_queries_run_correctly(self, domain, input_cases, xpath_query, query_outputs):
        for case in input_cases:
            self._make_case(domain, case)
        self._bootstrap_cases_in_es_for_domain(domain)
        self.elasticsearch.indices.refresh(CASE_SEARCH_INDEX)
        for query, output in query_outputs:
            self.assertItemsEqual(
                query.get_ids(),
                output
            )
        if xpath_query:
            self.assertItemsEqual(
                CaseSearchES().xpath_query(self.domain, xpath_query).get_ids(),
                output
            )

    def test_simple_case_property_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'foo': 'redbeard'},
                {'_id': 'c2', 'foo': 'blackbeard'},
            ],
            CaseSearchES().domain(self.domain).case_property_query("foo", "redbeard"),
            "foo = 'redbeard'",
            ['c1']
        )

    def test_fuzzy_case_property_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'foo': 'redbeard'},
                {'_id': 'c2', 'foo': 'blackbeard'},
            ],
            CaseSearchES().domain(self.domain).case_property_query("foo", "backbeard", fuzzy=True),
            None,
            ['c2']
        )

    def test_regex_case_property_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'foo': 'redbeard'},
                {'_id': 'c2', 'foo': 'blackbeard'},
                {'_id': 'c3', 'foo': 'redblack'},
            ],
            CaseSearchES().domain(self.domain).regexp_case_property_query("foo", ".*beard.*"),
            None,
            ['c1', 'c2']
        )

    def test_casesearch_criteria_standard(self):
        config, _ = CaseSearchConfig.objects.get_or_create(pk=self.domain, enabled=True)
        data = [
            {'_id': 'rr', 'foo': 'red'},
            {'_id': 'rb', 'foo': 'red beard'},
            {'_id': 'crb', 'foo': 'Red Beard'},
            {'_id': 'bb', 'foo': 'black beard'},
            {'_id': 'rc', 'foo': 'red color'},
            {'_id': 'an', 'foo': 'Alfred Nemo'},
            {'_id': 'wb', 'foo': 'White bear'},
        ]
        query_matches = [
            ({'foo': 'red'}, ['r']),
            ({'foo': 'red beard'}, ['rb']),
            ({'foo': 'red bear'}, []),
            ({'foo': 'beard'}, []),
            ({'foo': 'bear'}, []),
        ]
        self._assert_queries_run_correctly(
            self.domain,
            data,
            None,
            [
                (
                    CaseSearchCriteria(self.domain, self.case_type, criteria).search_es,
                    output
                )
                for criteria, output in query_matches
            ]
        )
        config.delete()

    @flag_enabled('USH_WILDCARD_SEARCH')
    def test_casesearch_criteria_advanced(self):
        fp, _ = FuzzyProperties.objects.get_or_create(
            domain=self.domain, case_type=self.case_type, properties=['foo'])
        config, _ = CaseSearchConfig.objects.get_or_create(pk=self.domain, enabled=True)
        config.fuzzy_properties.add(fp)
        data = [
            {'_id': 'rb', 'foo': 'red beard'},
            {'_id': 'crb', 'foo': 'Red Beard'},
            {'_id': 'bb', 'foo': 'black beard'},
            {'_id': 'rc', 'foo': 'red color'},
            {'_id': 'an', 'foo': 'Alfred Nemo'},
            {'_id': 'wb', 'foo': 'White bear'},
        ]
        query_matches = [
            ({'foo': 'red'}, ['rb', 'crb', 'an', 'rc']),
            ({'foo': 'red beard'}, ['rb', 'crb']),
            ({'foo': 'red bear'}, ['rb', 'crb']),
            ({'foo': 'red colour'}, []),  # fuzzy doesn't work on phrases
            ({'foo': 'colour'}, ['rc']),  # fuzzy works on words
            ({'foo': 'beard'}, ['rb', 'crb', 'bb', 'wb']),
            ({'foo': 'bear'}, ['rb', 'crb', 'bb', 'wb']),
        ]
        self._assert_queries_run_correctly(
            self.domain,
            data,
            None,
            [
                (
                    CaseSearchCriteria(self.domain, self.case_type, criteria).search_es,
                    output
                )
                for criteria, output in query_matches
            ]
        )
        fp.delete()
        config.delete()

    def test_multiple_case_search_queries(self):
        query = (CaseSearchES().domain(self.domain)
                 .case_property_query("foo", "redbeard")
                 .case_property_query("parrot_name", "polly"))
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'foo': 'redbeard', 'parrot_name': 'polly'},
                {'_id': 'c2', 'foo': 'blackbeard', 'parrot_name': 'polly'},
                {'_id': 'c3', 'foo': 'redbeard', 'parrot_name': 'molly'}
            ],
            query,
            "foo = 'redbeard' and parrot_name = 'polly'",
            ['c1']
        )

    def test_multiple_case_search_queries_should_clause(self):
        query = (CaseSearchES().domain(self.domain)
                 .case_property_query("foo", "redbeard")
                 .case_property_query("parrot_name", "polly", clause="should"))
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'foo': 'redbeard', 'parrot_name': 'polly'},
                {'_id': 'c2', 'foo': 'blackbeard', 'parrot_name': 'polly'},
                {'_id': 'c3', 'foo': 'redbeard', 'parrot_name': 'molly'}
            ],
            query,
            None,
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
            None,
            ['c2']
        )

    def test_missing_case_property(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c2', 'foo': 'blackbeard'},
                {'_id': 'c3', 'foo': ''},
                {'_id': 'c4'},
            ],
            CaseSearchES().domain(self.domain).filter(case_property_missing('foo')),
            "foo = ''",
            ['c3', 'c4']
        )

    def test_full_text_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'description': 'redbeards are red'},
                {'_id': 'c2', 'description': 'blackbeards are black'},
            ],
            CaseSearchES().domain(self.domain).filter(case_property_text_query('description', 'red')),
            None,
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
            'num <= 3 and num >= 2',
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
            "dob >= '2020-03-02' and dob <= '2020-03-03'",
            ['c2', 'c3']
        )
