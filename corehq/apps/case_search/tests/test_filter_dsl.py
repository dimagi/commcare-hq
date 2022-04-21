from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from eulxml.xpath import parse as parse_xpath
from freezegun import freeze_time

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from corehq.apps.es import filters
from couchforms.geopoint import GeoPoint
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.case_search.filter_dsl import (
    SearchFilterContext,
    build_filter_from_ast,
)
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_geo_distance,
    case_property_query,
    reverse_index_case_query,
)
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.es.elasticsearch import ConnectionError
from corehq.util.test_utils import trap_extra_setup


@es_test
class TestFilterDsl(ElasticTestMixin, SimpleTestCase):

    def test_simple_filter(self):
        parsed = parse_xpath("name = 'farid'")

        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "filter": (
                                        {
                                            "term": {
                                                "case_properties.key.exact": "name"
                                            }
                                        },
                                        {
                                            "term": {
                                                "case_properties.value.exact": "farid"
                                            }
                                        }
                                    )
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
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_simple_fuzzy_filter(self):
        parsed = parse_xpath("name = 'farid'")

        expected_filter = case_property_query("name", "farid", fuzzy=True)
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain", {"name"}))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_ancestor_filter(self):
        parsed = parse_xpath("parent/name = 'farid'")

        expected_filter = reverse_index_case_query(["123"], "parent")

        with patch("corehq.apps.case_search.filter_dsl._do_parent_lookup") as parent_lookup:
            parent_lookup.return_value = ["123"]
            built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))

        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
        domain_arg, parent_built_filter, raw_query = parent_lookup.call_args.args
        self.assertEqual(domain_arg, "domain")
        self.assertEqual(raw_query, 'name = "farid"')

        expected_parent_filter = case_property_query("name", "farid", fuzzy=False)
        self.checkQuery(parent_built_filter, expected_parent_filter, is_raw_query=True)

    def test_ancestor_fuzzy_filter(self):
        parsed = parse_xpath("parent/name = 'farid'")

        expected_filter = reverse_index_case_query(["123"], "parent")

        with patch("corehq.apps.case_search.filter_dsl._do_parent_lookup") as parent_lookup:
            parent_lookup.return_value = ["123"]
            built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain", {"name"}))

        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
        domain_arg, parent_built_filter, raw_query = parent_lookup.call_args.args
        self.assertEqual(domain_arg, "domain")
        self.assertEqual(raw_query, 'name = "farid"')

        expected_parent_filter = case_property_query("name", "farid", fuzzy=False)
        self.checkQuery(parent_built_filter, expected_parent_filter, is_raw_query=True)

    def test_subcase_fuzzy_filter(self):
        """Fuzzy filtering not applied to subcase queries"""
        parsed = parse_xpath("subcase-exists('father', @case_type = 'child' and name='Margaery')")

        def _build_mock_fn(expected_return):
            """Calls the real function and tests the returned value"""
            def _mock_build_filter_check_result(*args, **kwargs):
                result = build_filter_from_ast(*args, **kwargs)
                self.checkQuery(result, expected_return, is_raw_query=True)
                return result

            return _mock_build_filter_check_result

        expected = filters.AND(
            case_property_query("@case_type", "child"),
            case_property_query("name", "Margaery"),
        )
        module_path = "corehq.apps.case_search.xpath_functions.subcase_functions"
        with patch(f"{module_path}._build_subcase_filter_from_ast", new=_build_mock_fn(expected)), \
             patch(f"{module_path}._get_parent_case_ids", return_value=["123"]):

            built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain", {"name"}))

        expected_filter = filters.doc_id(["123"])
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_not_filter(self):
        parsed = parse_xpath("not(name = 'farid')")

        expected_filter = {
            "bool": {
                "must_not": {
                    "nested": {
                        "path": "case_properties",
                        "query": {
                            "bool": {
                                "filter": [
                                    {
                                        "bool": {
                                            "filter": (
                                                {
                                                    "term": {
                                                        "case_properties.key.exact": "name"
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "case_properties.value.exact": "farid"
                                                    }
                                                }
                                            )
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
            }
        }
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_date_comparison(self):
        parsed = parse_xpath("dob >= '2017-02-12'")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "dob"
                                }
                            }
                        ],
                        "must": {
                            "range": {
                                "case_properties.value.date": {
                                    "gte": "2017-02-12"
                                }
                            }
                        }
                    }
                }
            }
        }
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    @freeze_time('2021-08-02')
    def test_date_comparison__today(self):
        parsed = parse_xpath("dob >= today()")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "dob"
                                }
                            }
                        ],
                        "must": {
                            "range": {
                                "case_properties.value.date": {
                                    "gte": "2021-08-02"
                                }
                            }
                        }
                    }
                }
            }
        }
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    def test_numeric_comparison(self):
        parsed = parse_xpath("number <= '100.32'")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "number"
                                }
                            }
                        ],
                        "must": {
                            "range": {
                                "case_properties.value.numeric": {
                                    "lte": 100.32
                                }
                            }
                        }
                    }
                }
            }
        }
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    def test_numeric_comparison_negative(self):
        parsed = parse_xpath("number <= -100.32")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "number"
                                }
                            }
                        ],
                        "must": {
                            "range": {
                                "case_properties.value.numeric": {
                                    "lte": -100.32
                                }
                            }
                        }
                    }
                }
            }
        }
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    def test_numeric_equality_negative(self):
        parsed = parse_xpath("number = -100.32")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "filter": (
                                        {
                                            "term": {
                                                "case_properties.key.exact": "number"
                                            }
                                        },
                                        {
                                            "term": {
                                                "case_properties.value.exact": -100.32
                                            }
                                        }
                                    )
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
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_case_property_existence(self):
        parsed = parse_xpath("property != ''")
        expected_filter = {
            "bool": {
                "must_not": {
                    "bool": {
                        "should": [
                            {
                                "bool": {
                                    "must_not": {
                                        "nested": {
                                            "path": "case_properties",
                                            "query": {
                                                "bool": {
                                                    "filter": [
                                                        {
                                                            "term": {
                                                                "case_properties.key.exact": "property"
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
                                }
                            },
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
                                                                    "case_properties.key.exact": "property"
                                                                }
                                                            },
                                                            {
                                                                "term": {
                                                                    "case_properties.value.exact": ""
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
        }

        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    def test_nested_filter(self):
        parsed = parse_xpath("(name = 'farid' or name = 'leila') and dob <= '2017-02-11'")
        expected_filter = {
            "bool": {
                "filter": [
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
                                                        "bool": {
                                                            "filter": [
                                                                {
                                                                    "term": {
                                                                        "case_properties.key.exact": "name"
                                                                    }
                                                                },
                                                                {
                                                                    "term": {
                                                                        "case_properties.value.exact": "farid"
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
                                },
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
                                                                        "case_properties.value.exact": "leila"
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
                    },
                    {
                        "nested": {
                            "path": "case_properties",
                            "query": {
                                "bool": {
                                    "filter": [
                                        {
                                            "term": {
                                                "case_properties.key.exact": "dob"
                                            }
                                        }
                                    ],
                                    "must": {
                                        "range": {
                                            "case_properties.value.date": {
                                                "lte": "2017-02-11"
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

        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_selected(self):
        parsed = parse_xpath("selected(first_name, 'Jon')")
        expected_filter_single = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "first_name"
                                }
                            }
                        ],
                        "must": {
                            "match": {
                                "case_properties.value": {
                                    "query": "Jon",
                                    "operator": "or",
                                    "fuzziness": "0"
                                }
                            }
                        }
                    }
                }
            }
        }

        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter_single, built_filter, is_raw_query=True)

        parsed = parse_xpath("selected(first_name, 'Jon John Jhon')")
        expected_filter_many = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "first_name"
                                }
                            }
                        ],
                        "must": {
                            "match": {
                                "case_properties.value": {
                                    "query": "Jon John Jhon",
                                    "operator": "or",
                                    "fuzziness": "0"
                                }
                            }
                        }
                    }
                }
            }
        }

        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter_many, built_filter, is_raw_query=True)

    def test_selected_any(self):
        parsed = parse_xpath("selected-any(first_name, 'Jon John Jhon')")
        expected_filter = {
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
                                                "case_properties.key.exact": "first_name"
                                            }
                                        }
                                    ],
                                    "must": {
                                        "match": {
                                            "case_properties.value": {
                                                "query": "Jon John Jhon",
                                                "operator": "or",
                                                "fuzziness": "AUTO"
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    },
                    {
                        "nested": {
                            "path": "case_properties",
                            "query": {
                                "bool": {
                                    "filter": [
                                        {
                                            "term": {
                                                "case_properties.key.exact": "first_name"
                                            }
                                        }
                                    ],
                                    "must": {
                                        "match": {
                                            "case_properties.value": {
                                                "query": "Jon John Jhon",
                                                "operator": "or",
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

        # Note fuzzy is on for this one
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain", {"first_name"}))
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)

    def test_selected_all(self):
        parsed = parse_xpath("selected-all(first_name, 'Jon John Jhon')")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "first_name"
                                }
                            }
                        ],
                        "must": {
                            "match": {
                                "case_properties.value": {
                                    "query": "Jon John Jhon",
                                    "operator": "and",
                                    "fuzziness": "0"
                                }
                            }
                        }
                    }
                }
            }
        }

        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)

    def test_self_reference(self):
        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(parse_xpath("name = other_property"), SearchFilterContext("domain"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(parse_xpath("name > other_property"), SearchFilterContext("domain"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(parse_xpath("parent/name > other_property"), SearchFilterContext("domain"))

    @freeze_time('2021-08-02')
    def test_filter_today(self):
        parsed = parse_xpath("age > today()")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "age"
                                }
                            }
                        ],
                        "must": {
                            "range": {
                                "case_properties.value.date": {
                                    "gt": "2021-08-02"
                                }
                            }
                        }
                    }
                }
            }
        }

        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)

    @freeze_time('2021-08-02')
    def test_filter_date_today(self):
        parsed = parse_xpath("age > date(today())")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "case_properties.key.exact": "age"
                                }
                            }
                        ],
                        "must": {
                            "range": {
                                "case_properties.value.date": {
                                    "gt": "2021-08-02"
                                }
                            }
                        }
                    }
                }
            }
        }

        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)

    def test_within_distance_filter(self):
        parsed = parse_xpath("within-distance(coords, '42.4402967 -71.1453275', 1, 'miles')")
        expected_filter = case_property_geo_distance('coords', GeoPoint(42.4402967, -71.1453275), miles=1.0)
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)


@es_test
class TestFilterDslLookups(ElasticTestMixin, TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestFilterDslLookups, cls).setUpClass()
        with trap_extra_setup(ConnectionError):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, CASE_SEARCH_INDEX_INFO)

        cls.child_case1_id = 'margaery'
        cls.child_case2_id = 'loras'
        cls.parent_case_id = 'mace'
        cls.grandparent_case_id = 'olenna'
        cls.domain = "Tyrell"
        factory = CaseFactory(domain=cls.domain)
        grandparent_case = CaseStructure(
            case_id=cls.grandparent_case_id,
            attrs={
                'create': True,
                'case_type': 'grandparent',
                'update': {
                    "name": "Olenna",
                    "alias": "Queen of thorns",
                    "house": "Tyrell",
                },
            })

        parent_case = CaseStructure(
            case_id=cls.parent_case_id,
            attrs={
                'create': True,
                'case_type': 'parent',
                'update': {
                    "name": "Mace",
                    "house": "Tyrell",
                },
            },
            indices=[CaseIndex(
                grandparent_case,
                identifier='mother',
                relationship='child',
            )])

        child_case1 = CaseStructure(
            case_id=cls.child_case1_id,
            attrs={
                'create': True,
                'case_type': 'child',
                'update': {
                    "name": "Margaery",
                    "house": "Tyrell",
                },
            },
            indices=[CaseIndex(
                parent_case,
                identifier='father',
                relationship='extension',
            )],
        )
        child_case2 = CaseStructure(
            case_id=cls.child_case2_id,
            attrs={
                'create': True,
                'case_type': 'child',
                'update': {
                    "name": "Loras",
                    "house": "Tyrell",
                },
            },
            indices=[
                CaseIndex(
                    parent_case,
                    identifier='father',
                    relationship='extension',
                ),
                CaseIndex(
                    grandparent_case,
                    identifier='grandmother',
                    relationship='child',
                )
            ],
            walk_related=False,
        )
        for case in factory.create_or_update_cases([child_case1, child_case2]):
            send_to_elasticsearch('case_search', transform_case_for_elasticsearch(case.to_json()))
        cls.es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

    @classmethod
    def tearDownClass(self):
        FormProcessorTestUtils.delete_all_cases()
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        super(TestFilterDslLookups, self).tearDownClass()

    def test_parent_lookups(self):
        parsed = parse_xpath("father/name = 'Mace'")
        # return all the cases who's parent (relationship named 'father') has case property 'name' = 'Mace'

        expected_filter = {
            "nested": {
                "path": "indices",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "filter": (
                                        {
                                            "terms": {
                                                "indices.referenced_id": [self.parent_case_id]
                                            }
                                        },
                                        {
                                            "term": {
                                                "indices.identifier": "father"
                                            }
                                        }
                                    )
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
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
        self.assertEqual([self.child_case1_id, self.child_case2_id], CaseSearchES().filter(built_filter).values_list('_id', flat=True))

    def test_nested_parent_lookups(self):
        parsed = parse_xpath("father/mother/house = 'Tyrell'")

        expected_filter = {
            "nested": {
                "path": "indices",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "filter": (
                                        {
                                            "terms": {
                                                "indices.referenced_id": [self.parent_case_id]
                                            }
                                        },
                                        {
                                            "term": {
                                                "indices.identifier": "father"
                                            }
                                        }
                                    )
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
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
        self.assertEqual([self.child_case1_id, self.child_case2_id], CaseSearchES().filter(built_filter).values_list('_id', flat=True))

    def test_subcase_exists(self):
        parsed = parse_xpath("subcase-exists('father', name='Margaery')")
        expected_filter = {"terms": {"_id": [self.parent_case_id]}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_exists__filter_no_match(self):
        parsed = parse_xpath("subcase-exists('father', name='Mace')")
        expected_filter = {"terms": {"_id": []}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_exists__no_subase_filter(self):
        parsed = parse_xpath("subcase-exists('father')")
        expected_filter = {"terms": {"_id": [self.parent_case_id]}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_exists_inverted(self):
        parsed = parse_xpath("not(subcase-exists('father', name='Margaery'))")
        expected_filter = {"bool": {"must_not": {"terms": {"_id": [self.parent_case_id]}}}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count__no_subcase_filter(self):
        parsed = parse_xpath("subcase-count('father') > 1")
        expected_filter = {"terms": {"_id": [self.parent_case_id]}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count__filter_no_match(self):
        parsed = parse_xpath("subcase-count('father', house='Martel') > 0")
        expected_filter = {"terms": {"_id": []}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_gt(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') > 1")
        expected_filter = {"terms": {"_id": [self.parent_case_id]}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_lt(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') < 1")
        expected_filter = {"bool": {"must_not": {"terms": {"_id": [self.parent_case_id]}}}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_lt_no_match(self):
        """Subcase filter matches no cases and since it's an 'inverted' filter (lt)
        we don't need to apply any filtering to the parent query"""
        parsed = parse_xpath("subcase-count('father', house='Reyne') < 1")
        expected_filter = {"match_all": {}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_no_match(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') > 2")
        expected_filter = {"terms": {"_id": []}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_eq(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') = 2")
        expected_filter = {"terms": {"_id": [self.parent_case_id]}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_filter_relationship(self):
        parsed = parse_xpath("subcase-count('grandmother', house='Tyrell') >= 1")
        expected_filter = {"terms": {"_id": [self.grandparent_case_id]}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_filter_relationship_no_hits(self):
        parsed = parse_xpath("subcase-count('grandmother', house='Tyrell') > 1")
        expected_filter = {"terms": {"_id": []}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
