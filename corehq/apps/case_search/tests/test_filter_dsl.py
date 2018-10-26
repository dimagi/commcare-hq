from __future__ import absolute_import, unicode_literals

from django.test import SimpleTestCase, TestCase
from elasticsearch.exceptions import ConnectionError
from eulxml.xpath import parse as parse_xpath

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from corehq.apps.case_search.filter_dsl import (
    CaseFilterError,
    build_filter_from_ast,
    get_properties_from_ast,
)
from corehq.apps.es import CaseSearchES
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import generate_cases, trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping


class TestFilterDsl(SimpleTestCase):
    def test_simple_filter(self):
        parsed = parse_xpath("name = 'farid'")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "filtered": {
                        "query": {
                            "match_all": {}
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
                                        "case_properties.value.exact": "farid"
                                    }
                                }
                            )
                        }
                    }
                }
            }
        }
        built_filter = build_filter_from_ast("domain", parsed)
        self.assertEqual(expected_filter, built_filter)

    def test_date_comparison(self):
        parsed = parse_xpath("dob >= '2017-02-12'")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "filtered": {
                        "filter": {
                            "term": {
                                "case_properties.key.exact": "dob"
                            }
                        },
                        "query": {
                            "range": {
                                "case_properties.value.date": {
                                    "gte": "2017-02-12",
                                }
                            }
                        }
                    }
                }
            }
        }
        self.assertEqual(expected_filter, build_filter_from_ast("domain", parsed))

    def test_numeric_comparison(self):
        parsed = parse_xpath("number <= '100.32'")
        expected_filter = {
            "nested": {
                "path": "case_properties",
                "query": {
                    "filtered": {
                        "filter": {
                            "term": {
                                "case_properties.key.exact": "number"
                            }
                        },
                        "query": {
                            "range": {
                                "case_properties.value.numeric": {
                                    "lte": 100.32,
                                }
                            }
                        }
                    }
                }
            }
        }
        self.assertEqual(expected_filter, build_filter_from_ast("domain", parsed))

    def test_case_property_existence(self):
        parsed = parse_xpath("property != ''")
        expected_filter = {
            "not": {
                "or": (
                    {
                        "not": {
                            "nested": {
                                "path": "case_properties",
                                "query": {
                                    "filtered": {
                                        "query": {
                                            "match_all": {
                                            }
                                        },
                                        "filter": {
                                            "term": {
                                                "case_properties.key.exact": "property"
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
                                    "query": {
                                        "match_all": {
                                        }
                                    },
                                    "filter": {
                                        "and": (
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
                                        )
                                    }
                                }
                            }
                        }
                    }
                )
            }
        }

        self.assertEqual(expected_filter, build_filter_from_ast("domain", parsed))


    def test_nested_filter(self):
        parsed = parse_xpath("(name = 'farid' or name = 'leila') and dob <= '2017-02-11'")
        expected_filter = {
            "and": (
                {
                    "or": (
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
                                                        "case_properties.value.exact": "farid"
                                                    }
                                                }
                                            )
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
                                                        "case_properties.value.exact": "leila"
                                                    }
                                                }
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    )
                },
                {
                    "nested": {
                        "path": "case_properties",
                        "query": {
                            "filtered": {
                                "filter": {
                                    "term": {
                                        "case_properties.key.exact": "dob"
                                    }
                                },
                                "query": {
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
            )
        }

        built_filter = build_filter_from_ast("domain", parsed)
        self.assertEqual(expected_filter, built_filter)

    def test_self_reference(self):
        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(None, parse_xpath("name = other_property"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(None, parse_xpath("name > other_property"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(None, parse_xpath("parent/name > other_property"))

    def test_parent_property_lookup(self):
        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(None, parse_xpath("parent/name = 'foo'"))


class TestGetProperties(SimpleTestCase):
    pass


@generate_cases([
    # equality
    ("property = 'value'", ['property']),
    # comparison
    ("property > 100", ['property']),
    # complex expression
    ("first_property > 100 or second_property = 'foo' and third_property = 'bar'",
     ['first_property', 'second_property', 'third_property']),
    # malformed expression
    ("foo = 'bar' or baz = buzz or ham = 'spam' and eggs", ['foo', 'baz', 'ham']),
    # related case lookup
    ("parent/parent/foo = 'bar' and parent/baz = 'buzz'", ['parent/parent/foo', 'parent/baz']),
    # duplicate properties
    ("property = 'value' or property = 'other_value'", ['property']),
], TestGetProperties)
def test_get_properties_from_ast(self, expression, expected_values):
    self.assertEqual(set(expected_values), set(get_properties_from_ast(parse_xpath(expression))))
