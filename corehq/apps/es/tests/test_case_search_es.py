import uuid
from collections import Counter
from datetime import date

from django.test import TestCase
from django.test.testcases import SimpleTestCase

from unittest.mock import MagicMock, patch

from casexml.apps.case.models import CommCareCase
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.app_manager.models import (
    Application,
    CaseSearchProperty,
    DetailColumn,
    Module,
)
from corehq.apps.case_search.const import IS_RELATED_CASE, RELEVANCE_SCORE
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
)
from corehq.apps.case_search.utils import (
    CaseSearchCriteria,
    _QueryHelper,
    get_related_case_relationships,
    get_related_case_results,
    get_related_cases,
)
from corehq.apps.es import queries
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_missing,
    case_property_range_query,
    case_property_text_query,
    case_search_to_case_json,
    flatten_result,
)
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.elastic import SIZE_LIMIT, get_es_new
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import CaseSearchReindexerFactory
from corehq.pillows.mappings.case_search_mapping import (
    CASE_SEARCH_INDEX,
    CASE_SEARCH_INDEX_INFO,
)
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import create_and_save_a_case


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
                                    "bool": {
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


class TestCaseSearchHitConversions(SimpleTestCase):
    maxDiff = None

    def test_case_search_to_case_json(self):
        value = case_search_to_case_json(self.make_hit())
        self.assertEqual(value, self.make_case_dict())

        case = CommCareCaseSQL(**value)
        self.assertEqual(case.case_id, '2a3341db-0ca4-444b-a44c-3bde3a16954e')
        self.assertEqual(case.case_json, self.make_case_dict()["case_json"])

    def test_case_search_to_case_json_include_score(self):
        actual = case_search_to_case_json(self.make_hit(), include_score=True)
        self.assertEqual(actual["case_json"][RELEVANCE_SCORE], "1.095")

    def test_case_search_to_case_json_is_related_case(self):
        actual = case_search_to_case_json(self.make_hit(), is_related_case=True)
        self.assertEqual(actual["case_json"][IS_RELATED_CASE], 'true')

    @staticmethod
    def make_hit():
        return {
            "_score": "1.095",
            "_source": {
                '_id': '2a3341db-0ca4-444b-a44c-3bde3a16954e',
                'name': 'blah',
                'closed': 'true',
                'doc_type': 'CommCareCase',
                'domain': 'healsec',
                'modified_on': '2016-05-31 00:00:00',
                '@indexed_on': '2020-04-18T12:34:56Z',
                'case_properties': [
                    {'key': '@case_id', 'value': 'should be removed'},
                    {'key': 'name', 'value': 'should be removed'},
                    {'key': 'case_name', 'value': 'should be removed'},
                    {'key': 'last_modified', 'value': 'should be removed'},
                    {'key': 'closed', 'value': 'nope'},
                    {'key': 'doc_type', 'value': 'frankle'},
                    {'key': 'domain', 'value': 'batter'},
                    {'key': 'foo', 'value': 'bar'},
                    {'key': 'baz', 'value': 'buzz'},
                ],
            },
        }

    @staticmethod
    def make_case_dict():
        return {
            'case_id': '2a3341db-0ca4-444b-a44c-3bde3a16954e',
            'name': 'blah',
            'closed': 'true',
            'domain': 'healsec',
            'modified_on': '2016-05-31 00:00:00',
            'case_json': {
                'closed': 'nope',
                'doc_type': 'frankle',
                'domain': 'batter',
                'foo': 'bar',
                'baz': 'buzz',
            },
        }


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

    def _make_case(self, domain, case_properties, index=None):
        # make a case
        case_properties = case_properties or {}
        case_id = case_properties.pop('_id')
        case_type = case_properties.pop('case_type', self.case_type)
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        owner_id = case_properties.pop('owner_id', None)
        case = create_and_save_a_case(
            domain, case_id, case_name, case_properties, owner_id=owner_id, case_type=case_type, index=index
        )
        return case

    def _bootstrap_cases_in_es_for_domain(self, domain, input_cases):
        for case in input_cases:
            index = case.pop('index', None)
            self._make_case(domain, case, index=index)
        with patch('corehq.pillows.case_search.domains_needing_search_index',
                   MagicMock(return_value=[domain])):
            CaseSearchReindexerFactory(domain=domain).build().reindex()
        self.elasticsearch.indices.refresh(CASE_SEARCH_INDEX)

    def _assert_query_runs_correctly(self, domain, input_cases, query, xpath_query, output):
        self._bootstrap_cases_in_es_for_domain(domain, input_cases)
        self.assertItemsEqual(
            query.get_ids(),
            output
        )
        if xpath_query:
            self.assertItemsEqual(
                CaseSearchES().xpath_query(self.domain, xpath_query).get_ids(),
                output
            )

    def _create_case_search_config(self):
        config, _ = CaseSearchConfig.objects.get_or_create(pk=self.domain, enabled=True)
        self.addCleanup(config.delete)
        return config

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
            CaseSearchES().domain(self.domain).add_query(
                case_property_range_query('dob', gte='2020-03-02', lte='2020-03-03'),
                clause=queries.MUST
            ),
            "dob >= '2020-03-02' and dob <= '2020-03-03'",
            ['c2', 'c3']
        )

    def test_date_range_criteria(self):
        self._create_case_search_config()
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'dob': date(2020, 3, 1)},
                {'_id': 'c2', 'dob': date(2020, 3, 2)},
                {'_id': 'c3', 'dob': date(2020, 3, 3)},
                {'_id': 'c4', 'dob': date(2020, 3, 4)},
            ],
            CaseSearchCriteria(self.domain, [self.case_type], {'dob': '__range__2020-03-02__2020-03-03'}).search_es,
            None,
            ['c2', 'c3']
        )

    def test_get_related_case_relationships(self):
        app = Application.new_app(self.domain, "Case Search App")
        module = app.add_module(Module.new_module("Search Module", "en"))
        module.case_type = self.case_type
        detail = module.case_details.short
        detail.columns.extend([
            DetailColumn(header={"en": "x"}, model="case", field="x", format="plain"),
            DetailColumn(header={"en": "y"}, model="case", field="parent/parent/y", format="plain"),
            DetailColumn(header={"en": "z"}, model="case", field="host/z", format="plain"),
        ])
        module.search_config.properties = [CaseSearchProperty(
            name="texture",
            label={"en": "Texture"},
        )]

        module = app.add_module(Module.new_module("Non-Search Module", "en"))
        module.case_type = self.case_type
        detail = module.case_details.short
        detail.columns.append(
            DetailColumn(header={"en": "zz"}, model="case", field="parent/zz", format="plain"),
        )

        self.assertEqual(get_related_case_relationships(app, self.case_type), {"parent/parent", "host"})
        self.assertEqual(get_related_case_relationships(app, "monster"), set())

    def test_get_related_case_results(self):
        # Note that cases must be defined before other cases can reference them
        cases = [
            {'_id': 'c1', 'case_type': 'monster', 'description': 'grandparent of first person'},
            {'_id': 'c2', 'case_type': 'monster', 'description': 'parent of first person', 'index': {
                'parent': ('monster', 'c1')
            }},
            {'_id': 'c3', 'case_type': 'monster', 'description': 'parent of host'},
            {'_id': 'c4', 'case_type': 'monster', 'description': 'host of second person', 'index': {
                'parent': ('monster', 'c3')
            }},
            {'_id': 'c5', 'description': 'first person', 'index': {
                'parent': ('monster', 'c2')
            }},
            {'_id': 'c6', 'description': 'second person', 'index': {
                'host': ('monster', 'c4')
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

        hits = CaseSearchES().domain(self.domain).case_type(self.case_type).run().hits
        cases = [CommCareCase.wrap(flatten_result(result)) for result in hits]
        self.assertEqual({case.case_id for case in cases}, {'c5', 'c6'})

        self._assert_related_case_ids(cases, set(), set())
        self._assert_related_case_ids(cases, {"parent"}, {"c2"})
        self._assert_related_case_ids(cases, {"host"}, {"c4"})
        self._assert_related_case_ids(cases, {"parent/parent"}, {"c1"})
        self._assert_related_case_ids(cases, {"host/parent"}, {"c3"})
        self._assert_related_case_ids(cases, {"host", "parent"}, {"c2", "c4"})
        self._assert_related_case_ids(cases, {"host", "parent/parent"}, {"c4", "c1"})

    def test_get_related_case_results_duplicates(self):
        """Test that `get_related_cases` does not include any cases that are in the initial
        set or are duplicates of others already found."""

        # d1 :> c2 > c1 > a1
        # d1 > c1
        # Search for case type 'c'
        # - initial results c1, c2
        # - related lookups (parent, parent/parent) yield a1, c1, a1
        # - child lookups yield c2, d1
        # - (future) extension lookups yield d1
        cases = [
            {'_id': 'a1', 'case_type': 'a'},
            {'_id': 'c1', 'case_type': 'c', 'index': {
                'parent': ('a', 'a1'),
            }},
            {'_id': 'c2', 'case_type': 'c', 'index': {
                'parent': ('c', 'c1'),
            }},
            {'_id': 'd1', 'case_type': 'd', 'index': {
                'parent': ('c', 'c1'),
                'host': ('c', 'c2'),
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

        hits = CaseSearchES().domain(self.domain).case_type("c").run().hits
        cases = [CommCareCase.wrap(flatten_result(result)) for result in hits]
        self.assertEqual({case.case_id for case in cases}, {'c1', 'c2'})

        with patch("corehq.apps.case_search.utils.get_related_case_relationships",
                   return_value={"parent", "parent/parent"}), \
             patch("corehq.apps.case_search.utils.get_child_case_types", return_value={"c", "d"}), \
             patch("corehq.apps.case_search.utils.get_app_cached"):
            cases = get_related_cases(_QueryHelper(self.domain), None, {"c"}, cases)

        case_ids = Counter([case.case_id for case in cases])
        self.assertEqual(set(case_ids), {"a1", "d1"})  # c1, c2 excluded since they are in the initial list
        self.assertEqual(max(case_ids.values()), 1, case_ids)  # no duplicates

    def _assert_related_case_ids(self, cases, paths, ids):
        results = get_related_case_results(_QueryHelper(self.domain), cases, paths)
        result_ids = Counter([result['_id'] for result in results])
        self.assertEqual(ids, set(result_ids))
        if result_ids:
            self.assertEqual(1, max(result_ids.values()), result_ids)  # no duplicates

    def test_fuzzy_properties(self):
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Neu York'},
            {'_id': 'c3', 'case_type': 'show', 'description': 'Boston'},
        ]
        config = self._create_case_search_config()
        fuzzy_properties = FuzzyProperties.objects.create(domain=self.domain, case_type='song', properties=['description'])
        config.fuzzy_properties.add(fuzzy_properties)
        self.addCleanup(fuzzy_properties.delete)
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            CaseSearchCriteria(self.domain, ['song', 'show'], {'description': 'New York'}).search_es,
            None,
            ['c1', 'c2']
        )

    def test_ignore_patterns(self):
        cases = [
            {'_id': 'c1', 'case_type': 'person', 'phone_number': '8675309'},
            {'_id': 'c2', 'case_type': 'person', 'phone_number': '9045555555'},
        ]
        config = self._create_case_search_config()
        pattern = IgnorePatterns.objects.create(
            domain=self.domain, case_type='person', case_property='phone_number', regex="+1")
        config.ignore_patterns.add(pattern)
        self.addCleanup(pattern.delete)
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            CaseSearchCriteria(self.domain, ['person'], {'phone_number': '+18675309'}).search_es,
            None,
            ['c1']
        )

    def test_multiple_case_types(self):
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Another Song'},
            {'_id': 'c3', 'case_type': 'show', 'description': 'New York'},
            {'_id': 'c4', 'case_type': 'show', 'description': 'Boston'},
        ]
        self._create_case_search_config()
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            CaseSearchCriteria(self.domain, ['show', 'song'], {'description': 'New York'}).search_es,
            None,
            ['c1', 'c3']
        )

    def test_blank_case_search(self):
        # foo = '' should match all cases where foo is empty or absent
        self._create_case_search_config()
        self._bootstrap_cases_in_es_for_domain(self.domain, [
            {'_id': 'c1', 'foo': 'redbeard'},
            {'_id': 'c2', 'foo': 'blackbeard'},
            {'_id': 'c3', 'foo': ''},
            {'_id': 'c4'},
        ])
        for criteria, expected in [
            ({'foo': ''}, ['c3', 'c4']),
            ({'foo': ['', 'blackbeard']}, ['c2', 'c3', 'c4']),
        ]:
            actual = CaseSearchCriteria(self.domain, [self.case_type], criteria).search_es.get_ids()
            msg = f"{criteria} yielded {actual}, not {expected}"
            self.assertItemsEqual(actual, expected, msg=msg)

    def test_blank_case_search_parent(self):
        self._create_case_search_config()
        self._bootstrap_cases_in_es_for_domain(self.domain, [
            {'_id': 'c1', 'foo': 'redbeard'},
            {'_id': 'c2', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c1')}},
            {'_id': 'c3', 'foo': 'blackbeard'},
            {'_id': 'c4', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c3')}},
            {'_id': 'c5', 'foo': ''},
            {'_id': 'c6', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c5')}},
            {'_id': 'c7'},
            {'_id': 'c8', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c7')}},
        ])
        actual = CaseSearchCriteria(self.domain, ['child'], {
            'parent/foo': ['', 'blackbeard'],
        }).search_es.get_ids()
        self.assertItemsEqual(actual, ['c4', 'c6', 'c8'])
