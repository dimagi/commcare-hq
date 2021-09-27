from django.test import SimpleTestCase, TestCase

from corehq.util.es.elasticsearch import ConnectionError
from eulxml.xpath import parse as parse_xpath

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.case_search.filter_dsl import (
    CaseFilterError,
    build_filter_from_ast,
)
from corehq.apps.es import CaseSearchES
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
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
        built_filter = build_filter_from_ast("domain", parsed)
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)

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
        self.checkQuery(expected_filter, build_filter_from_ast("domain", parsed), is_raw_query=True)

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
        self.checkQuery(expected_filter, build_filter_from_ast("domain", parsed), is_raw_query=True)

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
        self.checkQuery(expected_filter, build_filter_from_ast("domain", parsed), is_raw_query=True)

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
        built_filter = build_filter_from_ast("domain", parsed)
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)

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

        self.checkQuery(expected_filter, build_filter_from_ast("domain", parsed), is_raw_query=True)

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

        built_filter = build_filter_from_ast("domain", parsed)
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)

    def test_self_reference(self):
        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(None, parse_xpath("name = other_property"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(None, parse_xpath("name > other_property"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(None, parse_xpath("parent/name > other_property"))


@es_test
class TestFilterDslLookups(ElasticTestMixin, TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestFilterDslLookups, cls).setUpClass()
        with trap_extra_setup(ConnectionError):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, CASE_SEARCH_INDEX_INFO)

        cls.child_case_id = 'margaery'
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

        child_case = CaseStructure(
            case_id=cls.child_case_id,
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
        for case in factory.create_or_update_cases([child_case]):
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
        built_filter = build_filter_from_ast(self.domain, parsed)
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)
        self.assertEqual([self.child_case_id], CaseSearchES().filter(built_filter).values_list('_id', flat=True))

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
        built_filter = build_filter_from_ast(self.domain, parsed)
        self.checkQuery(expected_filter, built_filter, is_raw_query=True)
        self.assertEqual([self.child_case_id], CaseSearchES().filter(built_filter).values_list('_id', flat=True))
