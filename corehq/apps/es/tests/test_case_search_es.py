import uuid
from datetime import date, datetime
from unittest.mock import patch
import pytz

from django.test import TestCase
from django.test.testcases import SimpleTestCase

from couchforms.geopoint import GeoPoint

from corehq.apps.case_search.const import RELEVANCE_SCORE
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.case_search.xpath_functions.comparison import adjust_input_date_by_timezone
from corehq.apps.es import queries
from corehq.apps.es.client import manager
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_search_adapter,
    case_property_starts_with,
    case_property_geo_distance,
    case_property_missing,
    case_property_query,
    case_property_range_query,
    case_property_text_query,
    wrap_case_search_hit,
)
from corehq.apps.es.const import SIZE_LIMIT
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.form_processor.models import CommCareCaseIndex
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import CaseSearchReindexerFactory
from corehq.util.test_utils import create_and_save_a_case, flag_enabled


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
                                                    "bool": {
                                                        "should": [
                                                            {
                                                                "fuzzy": {
                                                                    "case_properties.value": {
                                                                        "value": "polly",
                                                                        "fuzziness": "AUTO",
                                                                        "max_expansions": 100
                                                                    }
                                                                }
                                                            },
                                                            {
                                                                "match": {
                                                                    "case_properties.value": {
                                                                        "query": "polly",
                                                                        "operator": "or",
                                                                        "fuzziness": "0"
                                                                    }
                                                                }
                                                            }
                                                        ]
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

    def test_blacklisted_owner_ids(self):
        query = self.es.domain('swashbucklers').blacklist_owner_id('123').owner('234')
        expected = {
            'query': {
                'bool': {
                    'filter': [
                        {'term': {'domain.exact': 'swashbucklers'}},
                        {'bool': {'must_not': {'term': {'owner_id': '123'}}}},
                        {'term': {'owner_id': '234'}},
                        {'match_all': {}}
                    ],
                    'must': {'match_all': {}},
                },
            },
            'size': SIZE_LIMIT,
        }
        self.checkQuery(query, expected, validate_query=False)


class TestCaseSearchHitConversions(SimpleTestCase):
    maxDiff = None

    def test_wrap_case_search_hit(self):
        case = wrap_case_search_hit(self.make_hit())
        self.assertEqual(case.case_id, '2a3341db-0ca4-444b-a44c-3bde3a16954e')
        self.assertEqual(case.closed, False)
        self.assertEqual(case.closed_by, None)
        self.assertEqual(case.closed_on, None)
        self.assertEqual(case.doc_type, 'CommCareCase')
        self.assertEqual(case.domain, 'healsec')
        self.assertEqual(case.external_id, None)
        self.assertEqual(case.location_id, None)
        self.assertEqual(case.modified_on, datetime(2019, 6, 21, 17, 32, 48))
        self.assertEqual(case.name, 'blah')
        self.assertEqual(case.opened_by, '29383d6a335847f985aeeeca94031f82')
        self.assertEqual(case.opened_on, datetime(2019, 6, 21, 17, 31, 18, 349000))
        self.assertEqual(case.owner_id, '29383d6a335847f985aeeeca94031f82')
        self.assertEqual(case.server_modified_on, datetime(2019, 6, 21, 17, 32, 48, 437901))
        self.assertEqual(case.type, 'mother')
        self.assertEqual(case.user_id, '29383d6a335847f985aeeeca94031f82')
        self.assertEqual(case.indices, [
            CommCareCaseIndex(
                case_id=case.case_id,
                domain='healsec',
                identifier='host',
                referenced_type='person',
                referenced_id='abc123',
                relationship_id=CommCareCaseIndex.EXTENSION,
            )
        ])
        self.assertEqual(case.case_json, {
            'closed': 'nope',
            'doc_type': 'frankle',
            'domain': 'batter',
            'foo': 'bar',
            'baz': 'buzz',
        })

    def test_wrap_case_search_hit_include_score(self):
        case = wrap_case_search_hit(self.make_hit(), include_score=True)
        self.assertEqual(case.case_json[RELEVANCE_SCORE], "1.095")

    @staticmethod
    def make_hit():
        return {
            "_score": "1.095",
            "_source": {
                '_id': '2a3341db-0ca4-444b-a44c-3bde3a16954e',
                'closed': False,
                'closed_by': None,
                'closed_on': None,
                'doc_type': 'CommCareCase',
                'domain': 'healsec',
                'external_id': None,
                'location_id': None,
                'modified_on': '2019-06-21T17:32:48Z',
                'name': 'blah',
                'opened_by': '29383d6a335847f985aeeeca94031f82',
                'opened_on': '2019-06-21T17:31:18.349000Z',
                'owner_id': '29383d6a335847f985aeeeca94031f82',
                'server_modified_on': '2019-06-21T17:32:48.437901Z',
                'type': 'mother',
                'user_id': '29383d6a335847f985aeeeca94031f82',
                '@indexed_on': '2020-04-18T12:34:56.332000Z',
                'indices': [
                    {
                        'case_id': '2a3341db-0ca4-444b-a44c-3bde3a16954e',
                        'domain': 'healsec',
                        'identifier': 'host',
                        'referenced_type': 'person',
                        'referenced_id': 'abc123',
                        'relationship': 'extension',
                    },
                ],
                'case_properties': [
                    {'key': '@case_id', 'value': '2a3341db-0ca4-444b-a44c-3bde3a16954e'},
                    {'key': '@case_type', 'value': 'mother'},
                    {'key': '@owner_id', 'value': '29383d6a335847f985aeeeca94031f82'},
                    {'key': '@status', 'value': 'open'},
                    {'key': 'name', 'value': 'blah'},
                    {'key': 'case_name', 'value': 'blah'},
                    {'key': 'external_id', 'value': None},
                    {'key': 'date_opened', 'value': '2019-06-21T17:31:18.349000Z'},
                    {'key': 'closed_on', 'value': None},
                    {'key': 'last_modified', 'value': '2019-06-21T17:32:48.332000Z'},
                    {'key': 'closed', 'value': 'nope'},
                    {'key': 'doc_type', 'value': 'frankle'},
                    {'key': 'domain', 'value': 'batter'},
                    {'key': 'foo', 'value': 'bar'},
                    {'key': 'baz', 'value': 'buzz'},
                ],
            },
        }


@es_test(requires=[case_search_adapter])
class BaseCaseSearchTest(TestCase):

    def setUp(self):
        self.domain = 'case_search_es'
        self.case_type = 'person'
        super(BaseCaseSearchTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases()

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
        CaseSearchReindexerFactory(domain=domain).build().reindex()
        manager.index_refresh(case_search_adapter.index_name)

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


class TestCaseSearchLookups(BaseCaseSearchTest):
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
            CaseSearchES().domain(self.domain).filter(case_property_range_query('num', gte=2, lte=3)),
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

    # Differs from above case_property_query because this is not an instance method but seperated from
    # the CaseSearchES class. More thorough testing of this method is in test_case_search_registry.py
    # and test_filter_dsl.py.
    def test_case_property_query(self):

        # mutlivalue_mode must be lowercase
        self.assertRaises(
            ValueError,
            lambda: case_property_query(
                'description',
                'redbeard blackbeard',
                multivalue_mode='AND'
            )
        )

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    @patch('corehq.pillows.case_search.get_gps_properties', return_value={'coords'})
    def test_geopoint_query_for_gps_properties(self, _):
        self._bootstrap_cases_in_es_for_domain(self.domain, [
            {'_id': 'c1', 'coords': "42.373611 -71.110558 0 0"},
            {'_id': 'c2', 'coords': "42 Wallaby Way"},
            {'_id': 'c3', 'coords': "-33.856159 151.215256 0 0"},
            {'_id': 'c4', 'coords': "-33.8373 151.225"},
        ])
        res = CaseSearchES().domain(self.domain).set_query(
            case_property_geo_distance('coords', GeoPoint(-33.1, 151.8), kilometers=1000),
        ).get_ids()
        self.assertItemsEqual(res, ['c3', 'c4'])

    @flag_enabled('GEOSPATIAL')
    @patch('corehq.pillows.case_search.get_geo_case_property', return_value='domain_coord')
    def test_geopoint_query_for_domain_geo_case_property(self, *args):
        self._bootstrap_cases_in_es_for_domain(self.domain, [
            {'_id': 'c1', 'domain_coord': "42 Wallaby Way"},
            {'_id': 'c2', 'domain_coord': "-33.856159 151.215256 0 0"},
        ])
        res = CaseSearchES().domain(self.domain).set_query(
            case_property_geo_distance('domain_coord', GeoPoint(-33.1, 151.8), kilometers=1000),
        ).get_ids()
        self.assertItemsEqual(res, ['c2'])

    def test_starts_with_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'ssn': '10'},
                {'_id': 'c2', 'ssn': "100"},
                {'_id': 'c3', 'ssn': '200'},
                {'_id': 'c4', 'ssn': '102'},
                {'_id': 'c5', 'ssn': '1001'},
                {'_id': 'c6', 'ssn': '100-1'},
            ],
            CaseSearchES().domain(self.domain).filter(
                case_property_starts_with('ssn', '100'),
            ),
            "starts-with(ssn, '100')",
            ['c5', 'c6', 'c2']
        )


class TestForwardTimezoneAdjustment(TestCase):

    def setUp(self):
        self.timezone = pytz.timezone('Asia/Seoul')  # UTC+0900
        super(TestForwardTimezoneAdjustment, self).setUp()

    def test_user_input_forward_timezone_adjustment_1(self):
        """Scenario 1:
        User input: last_modified < "2023-06-04"
        A case with last_modified displayed as 2023-06-04 is actually 2023-06-03T20:00:00 in ES
        Input modified to be last_modified < "2023-06-03T15:00:00" to exclude above case"""
        # user input: last_modified < '2023-06-04'
        self.assertEqual(datetime(2023, 6, 3, 15, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 4), self.timezone, '<'))

    def test_user_input_forward_timezone_adjustment_2(self):
        """Scenario 2:
        User input: last_modified > "2023-06-04"
        A case with last_modified displayed as 2023-06-05 is actually 2023-06-04T20:00:00 in ES
        Input modified to be last_modified > "2023-06-04T15:00:00" to include above case"""
        # user input: last_modified > '2023-06-04'
        self.assertEqual(datetime(2023, 6, 4, 15, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 4), self.timezone, '>'))

    def test_user_input_forward_timezone_adjustment_3(self):
        """Scenario 3:
        User input: last_modified <= "2023-06-04"
        A case with last_modified displayed as 2023-06-05 is actually 2023-06-04T20:00:00 in ES
        Input modified to be last_modified <= "2023-06-04T15:00:00" to exclude above case"""
        # user input: last_modified <= '2023-06-04'
        self.assertEqual(datetime(2023, 6, 4, 15, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 4), self.timezone, '<='))

    def test_user_input_forward_timezone_adjustment_4(self):
        """Scenario 4:
        User input: last_modified >= "2023-06-04"
        A case with last_modified displayed as 2023-06-04 is actually 2023-06-03T20:00:00 in ES
        Input modified to be last_modified >= "2023-06-03T15:00:00" to include above case"""
        # user input: last_modified >= '2023-06-04'
        self.assertEqual(datetime(2023, 6, 3, 15, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 4), self.timezone, '>='))


class TestBackwardTimezoneAdjustment(TestCase):

    def setUp(self):
        self.timezone = pytz.timezone('US/Hawaii')  # UTC-1000
        super(TestBackwardTimezoneAdjustment, self).setUp()

    def test_user_input_backwards_timezone_adjustment_1(self):
        """Scenario 1:
        User input = last_modified > "2023-06-03"
        A case with last_modified displayed as 2023-06-03 is actually 2023-06-04T05:00:00 in ES
        Input modified to be last_modified > "2023-06-04T10:00:00" to exclude above case"""
        # user input: last_modified > '2023-06-03'
        self.assertEqual(datetime(2023, 6, 4, 10, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 3), self.timezone, '>'))

    def test_user_input_backwards_timezone_adjustment_2(self):
        """Scenario 2:
        User input = last_modified < "2023-06-03"
        A case with last_modified displayed as 2023-06-02 is actually 2023-06-03T05:00:00 in ES
        Input modified to be last_modified > "2023-06-03T10:00:00" to include above case"""
        # user input: last_modified > '2023-06-03'
        self.assertEqual(datetime(2023, 6, 3, 10, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 3), self.timezone, '<'))

    def test_user_input_backwards_timezone_adjustment_3(self):
        """Scenario 3:
        User input = last_modified >= "2023-06-03"
        A case with last_modified displayed as 2023-06-02 is actually 2023-06-03T05:00:00 in ES
        Input modified to be last_modified > "2023-06-03T10:00:00" to exclude above case"""
        # user input: last_modified <= '2023-06-03'
        self.assertEqual(datetime(2023, 6, 3, 10, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 3), self.timezone, '>='))

    def test_user_input_backwards_timezone_adjustment_4(self):
        """Scenario 4:
        User input = last_modified <= "2023-06-03"
        A case with last_modified displayed as 2023-06-03 is actually 2023-06-04T05:00:00 in ES
        Input modified to be last_modified >= "2023-06-04T10:00:00" to include above case"""
        # user input: last_modified >= '2023-06-04'
        self.assertEqual(datetime(2023, 6, 4, 10, 0, 0),
                         adjust_input_date_by_timezone(date(2023, 6, 3), self.timezone, '<='))
