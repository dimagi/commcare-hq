from collections import OrderedDict

from django.test import TestCase

from corehq.apps.case_search.const import CASE_SEARCH_MAX_RESULTS
from corehq.apps.case_search.models import CaseSearchConfig, IgnorePatterns, _parse_commcare_sort_properties
from corehq.apps.case_search.tests.utils import get_case_search_query
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test

DOMAIN = 'mighty-search'


@es_test
class CaseSearchTests(ElasticTestMixin, TestCase):
    def setUp(self):
        super(CaseSearchTests, self).setUp()
        self.config, created = CaseSearchConfig.objects.get_or_create(pk=DOMAIN, enabled=True)

    def test_add_blacklisted_ids(self):
        criteria = {
            "commcare_blacklisted_owner_ids": "id1 id2 id3,id4"
        }
        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {'terms': {'domain.exact': [DOMAIN]}},
                        {"terms": {"type.exact": ["case_type"]}},
                        {"term": {"closed": False}},
                        {
                            "bool": {
                                "must_not": {
                                    "terms": {
                                        "owner_id": [
                                            "id1",
                                            "id2",
                                            "id3,id4"
                                        ]
                                    }
                                }
                            }
                        },
                        {"match_all": {}}
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "sort": [
                "_score",
                "_doc"
            ],
            "size": CASE_SEARCH_MAX_RESULTS
        }

        self.checkQuery(
            get_case_search_query(DOMAIN, ['case_type'], criteria),
            expected
        )

    def test_add_ignore_pattern_queries(self):
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='name',
            regex=' word',
        )                       # remove ' word' from the name case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='name',
            regex=' gone',
        )                       # remove ' gone' from the name case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='special_id',
            regex='-',
        )                       # remove '-' from the special id case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        self.config.save()
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='phone_number',
            regex='+',
        )                       # remove '+' from the phone_number case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        self.config.save()

        criteria = OrderedDict([
            ('phone_number', '+91999'),
            ('special_id', 'abc-123-546'),
            ('name', "this word should be gone"),
            ('other_name', "this word should not be gone"),
        ])

        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {'terms': {'domain.exact': [DOMAIN]}},
                        {"terms": {"type.exact": ["case_type"]}},
                        {"term": {"closed": False}},
                        {"match_all": {}}
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
                                                                        "case_properties.key.exact": "phone_number"
                                                                    }
                                                                },
                                                                {
                                                                    "term": {
                                                                        "case_properties.value.exact": "91999"
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
                                                                        "case_properties.key.exact": "special_id"
                                                                    }
                                                                },
                                                                {
                                                                    "term": {
                                                                        "case_properties.value.exact": "abc123546"
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
                                                                        "case_properties.value.exact": "this should be"  # noqa: E501
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
                                                                        "case_properties.key.exact": "other_name"
                                                                    }
                                                                },
                                                                {
                                                                    "term": {
                                                                        "case_properties.value.exact": "this word should not be gone"  # noqa: E501
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
            "sort": [
                "_score",
                "_doc"
            ],
            "size": CASE_SEARCH_MAX_RESULTS
        }
        self.checkQuery(
            get_case_search_query(DOMAIN, ['case_type'], criteria),
            expected,
            validate_query=False
        )

    def test_multi_xpath_query(self):
        criteria = OrderedDict([
            ('_xpath_query', ["name='Frodo Baggins'", "home='Hobbiton'"]),
        ])
        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {"terms": {"domain.exact": [DOMAIN]}},
                        {"terms": {"type.exact": ["case_type"]}},
                        {"term": {"closed": False}},
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
                                                                "case_properties.value.exact": "Frodo Baggins"
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
                                                                "case_properties.key.exact": "home"
                                                            }
                                                        },
                                                        {
                                                            "term": {
                                                                "case_properties.value.exact": "Hobbiton"
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
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "sort": [
                "_score",
                "_doc"
            ],
            "size": CASE_SEARCH_MAX_RESULTS
        }
        self.checkQuery(
            get_case_search_query(DOMAIN, ['case_type'], criteria),
            expected,
            validate_query=False
        )

    def test_indices_query(self):
        criteria = {
            "indices.parent": "id1"
        }
        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {'terms': {'domain.exact': [DOMAIN]}},
                        {"terms": {"type.exact": ["case_type"]}},
                        {"term": {"closed": False}},
                        {"match_all": {}}
                    ],
                    "must": {
                        "bool": {
                            "must": [
                                {
                                    "nested": {
                                        "path": "indices",
                                        "query": {
                                            "bool": {
                                                "filter": [
                                                    {
                                                        "bool": {
                                                            "filter": [
                                                                {
                                                                    "terms": {
                                                                        "indices.referenced_id": [
                                                                            "id1"
                                                                        ]
                                                                    }
                                                                },
                                                                {
                                                                    "term": {
                                                                        "indices.identifier": "parent"
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
            "sort": [
                "_score",
                "_doc"
            ],
            "size": CASE_SEARCH_MAX_RESULTS
        }

        self.checkQuery(
            get_case_search_query(DOMAIN, ['case_type'], criteria),
            expected,
            validate_query=False
        )

    def test_add_custom_sort_properties(self):
        criteria = {}
        commcare_sort = _parse_commcare_sort_properties(["name,-date_of_birth:date"])
        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {"terms": {"domain.exact": [DOMAIN]}},
                        {"terms": {"type.exact": ["case_type"]}},
                        {"term": {"closed": False}},
                        {"match_all": {}}
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "sort": [
                {
                    "case_properties.value.exact": {
                        "missing": "_first",
                        "order": "asc",
                        "nested_path": "case_properties",
                        "nested_filter": {
                            "term": {
                                "case_properties.key.exact": "name"
                            }
                        }
                    }
                },
                {
                    "case_properties.value.date": {
                        "missing": "_last",
                        "order": "desc",
                        "nested_path": "case_properties",
                        "nested_filter": {
                            "term": {
                                "case_properties.key.exact": "date_of_birth"
                            }
                        }
                    }
                }
            ],
            "size": CASE_SEARCH_MAX_RESULTS
        }

        self.checkQuery(
            get_case_search_query(DOMAIN, ['case_type'], criteria, commcare_sort=commcare_sort),
            expected
        )
