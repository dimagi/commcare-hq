from pprint import pformat
from corehq.apps.es.tests.utils import convert_to_es2


def eq(actual, expected, path=""):
    if actual == expected:
        return
    if isinstance(actual, dict) and isinstance(expected, dict):
        if actual.keys() == expected.keys():
            for key, a_val in actual.items():
                eq(a_val, expected[key], f"{path}.{key}" if path else key)
    if isinstance(actual, (list, tuple)) and isinstance(expected, (tuple, list)):
        if len(actual) == len(expected) and type(actual) == type(expected):
            for i, (ax, ex) in enumerate(zip(actual, expected)):
                eq(ax, ex, f"{path}[{i}]")
    assert 0, (
        f"\n\nnot equal {path}:\n"
        f"actual convert_to_es2(es7):\n"
        f"{pformat(actual, width=40)}\n"
        f"expected (es2):\n"
        f"{pformat(expected, width=40)}"
    )


def main():
    for description, es2_query, es7_query, convert in Queries():
        print(description)
        eq(convert(es7_query), es2_query)


CASE_SEARCH_MAX_RESULTS = SIZE_LIMIT = 1000000
_unique_names = {}


def check_query(test_path, strip_chars=0):
    def check_query(func):
        name = func.__name__
        if strip_chars:
            name = name[:-strip_chars]
            assert name in _unique_names, \
                f"wrong strip_chars value? {func.__name__} -> {name}"
        if func.__name__ in _unique_names:
            raise NameError(f"duplicate name: {test_path}:{name}")
        _unique_names[func.__name__] = f"{test_path}:{name}"
        return func
    return check_query


class Queries:

    def is_es7(self):
        return self.select == "es7"

    def __iter__(self):
        for name, description in _unique_names.items():
            self.select = "convert"
            convert = getattr(self, name)()
            assert callable(convert), name
            self.select = "es2"
            es2_query = getattr(self, name)()
            self.select = "es7"
            es7_query = getattr(self, name)()
            assert isinstance(es2_query, (dict, list)), f"{name} {es2_query}"
            assert isinstance(es7_query, (dict, list)), f"{name} {es7_query}"
            assert type(es7_query) == type(es2_query), f"{name} {es7_query} {es2_query}"
            assert es2_query != es7_query, name
            yield description, es2_query, es7_query, convert

    @check_query("corehq/apps/es/tests/test_aggregations.py")
    def test_nesting_aggregations(self):
        def convert(query):
            query = convert_to_es2(query)
            return query
        if self.select == "convert":
            return convert
        if self.is_es7():
            query = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "match_all": {}
                            }
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                }
            }
        else:
            query = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {
                                    "match_all": {}
                                }
                            ]
                        },
                        "query": {
                            "match_all": {}
                        }
                    }
                }
            }
        return query

    @check_query("corehq/apps/es/tests/test_case_search_es.py")
    def test_simple_case_property_query(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
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
        return json_output

    @check_query("corehq/apps/es/tests/test_case_search_es.py")
    def test_multiple_case_search_queries(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
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
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def _check_user_location_query(self, with_ids=True):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "should": (
                                        {
                                            "bool": {
                                                "filter": (
                                                    {"term": {"doc_type": "CommCareUser"}},
                                                    {"terms": {"assigned_location_ids": with_ids}})}
                                        },
                                        {
                                            "bool": {
                                                "filter": (
                                                    {"term": {"doc_type": "WebUser"}},
                                                    {"terms": {"domain_memberships.assigned_location_ids": with_ids}})}
                                        }
                                    )
                                }
                            },
                            {'term': {'base_doc': 'couchuser'}},
                            {'term': {'is_active': True}}
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                },
                "size": SIZE_LIMIT
            }
        else:
            json_output = {
                'query': {
                    'filtered': {
                        'filter': {
                            'and': [
                                {'or': (
                                    {'and': (
                                        {'term': {'doc_type': 'CommCareUser'}},
                                        {'terms': {'assigned_location_ids': with_ids}}
                                    )
                                    },
                                    {'and': (
                                        {'term': {'doc_type': 'WebUser'}},
                                        {'terms': {'domain_memberships.assigned_location_ids': with_ids}}
                                    )
                                    }
                                )},
                                {'term': {'base_doc': 'couchuser'}},
                                {'term': {'is_active': True}}
                            ]
                        },
                        'query': {'match_all': {}}}},
                'size': SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_basic_query(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "match_all": {}
                            }
                        ],
                        "must": {
                            "match_all": {}
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
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_query_size(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "match_all": {}
                            }
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                },
                "size": 0
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": 0
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_form_query(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"doc_type": "xforminstance"}},
                            {"exists": {"field": "xmlns"}},
                            {"exists": {"field": "form.meta.userID"}},
                            {"exists": {"field": "domain"}},
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                },
                "size": 1000000
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"term": {"doc_type": "xforminstance"}},
                                {"not": {"missing": {"field": "xmlns"}}},
                                {"not": {"missing": {"field": "form.meta.userID"}}},
                                {"not": {"missing": {"field": "domain"}}},
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_user_query(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "base_doc": "couchuser"
                                }
                            },
                            {
                                "term": {
                                    "is_active": True
                                }
                            }
                        ],
                        "must": {
                            "match_all": {}
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
                                {"term": {"base_doc": "couchuser"}},
                                {"term": {"is_active": True}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_filtered_forms(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"domain.exact": "zombocom"}},
                            {"term": {"xmlns.exact": "banana"}},
                            {"term": {"doc_type": "xforminstance"}},
                            {"exists": {"field": "xmlns"}},
                            {"exists": {"field": "form.meta.userID"}},
                            {"exists": {"field": "domain"}},
                        ],
                        "must": {
                            "match_all": {}
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
                                {"term": {"domain.exact": "zombocom"}},
                                {"term": {"xmlns.exact": "banana"}},
                                {"term": {"doc_type": "xforminstance"}},
                                {"not": {"missing": {"field": "xmlns"}}},
                                {"not": {"missing": {"field": "form.meta.userID"}}},
                                {"not": {"missing": {"field": "domain"}}},
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_sort(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
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
                    {
                        "timeEnd": {
                            "order": "asc"
                        }
                    }
                ],
                "size": SIZE_LIMIT
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT,
                "sort": [{
                    "timeEnd": {
                        "order": "asc"
                    }
                }],
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_cleanup_before_run(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "match_all": {}
                            }
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                },
                "size": SIZE_LIMIT,
                "aggs": {
                    "by_day": {
                        "date_histogram": {
                            "field": "date",
                            "interval": "day",
                            "time_zone": "-01:00"
                        }
                    }
                }
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "aggs": {
                    "by_day": {
                        "date_histogram": {
                            "field": "date",
                            "interval": "day",
                            "time_zone": "-01:00"
                        }
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_esquery.py")
    def test_exclude_source(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "domain.exact": "test-exclude"
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
                "size": SIZE_LIMIT,
                "_source": False
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {
                                    "term": {
                                        "domain.exact": "test-exclude"
                                    }
                                },
                                {
                                    "match_all": {}
                                }
                            ]
                        },
                        "query": {
                            "match_all": {}
                        }
                    }
                },
                "_source": False,
                "size": SIZE_LIMIT,
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_filters.py")
    def test_nested_filter(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "nested": {
                                    "path": "actions",
                                    "query": {
                                        "bool": {
                                            "filter": {
                                                "range": {
                                                    "actions.date": {
                                                        "gte": "2015-01-01",
                                                        "lt": "2015-02-01"
                                                    }
                                                }
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
                "size": SIZE_LIMIT
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"nested": {
                                    "path": "actions",
                                    "filter": {
                                        "range": {
                                            "actions.date": {
                                                "gte": "2015-01-01",
                                                "lt": "2015-02-01"
                                            }
                                        }
                                    }
                                }},
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_filters.py")
    def test_not_term_filter(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "must_not": {
                                        "term": {
                                            "type": "badcasetype"
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
                "size": SIZE_LIMIT
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {
                                    "not": {
                                        "term": {
                                            "type": "badcasetype"
                                        }
                                    }
                                },
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_filters.py")
    def test_not_or_rewrite(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "must_not": {
                                        "bool": {
                                            "should": [
                                                {
                                                    "term": {
                                                        "type": "A"
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "type": "B"
                                                    }
                                                }
                                            ]
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
                "size": SIZE_LIMIT
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {
                                    'and': (
                                        {
                                            "not": {
                                                "term": {
                                                    "type": "A"
                                                }
                                            }
                                        },
                                        {
                                            "not": {
                                                "term": {
                                                    "type": "B"
                                                }
                                            }
                                        },
                                    )
                                },
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_filters.py")
    def test_not_and_rewrite(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "must_not": {
                                        "bool": {
                                            "filter": [
                                                {
                                                    "term": {
                                                        "type": "A"
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "type": "B"
                                                    }
                                                }
                                            ]
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
                "size": SIZE_LIMIT
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {
                                    'or': (
                                        {
                                            "not": {
                                                "term": {
                                                    "type": "A"
                                                }
                                            }
                                        },
                                        {
                                            "not": {
                                                "term": {
                                                    "type": "B"
                                                }
                                            }
                                        },
                                    )
                                },
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_filters.py")
    def test_source_include(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "match_all": {}
                            }
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                },
                "size": SIZE_LIMIT,
                "_source": "source_obj"
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"match_all": {}}
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT,
                "_source": "source_obj"
            }
        return json_output

    @check_query("corehq/apps/es/tests/test_sms.py")
    def test_processed_or_incoming(self):
        def convert(json_output):
            json_output = convert_to_es2(json_output)
            return json_output
        if self.select == "convert":
            return convert
        if self.is_es7():
            json_output = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "domain.exact": "demo"
                                }
                            },
                            {
                                "bool": {
                                    "must_not": {
                                        "bool": {
                                            "filter": [
                                                {
                                                    "term": {
                                                        "direction": "o"
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "processed": False
                                                    }
                                                }
                                            ]
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
                "size": SIZE_LIMIT
            }
        else:
            json_output = {
                "query": {
                    "filtered": {
                        "filter": {
                            "and": [
                                {"term": {"domain.exact": "demo"}},
                                {
                                    "or": (
                                        {
                                            "not": {"term": {"direction": "o"}},
                                        },
                                        {
                                            "not": {"term": {"processed": False}},
                                        }
                                    ),
                                },
                                {"match_all": {}},
                            ]
                        },
                        "query": {"match_all": {}}
                    }
                },
                "size": SIZE_LIMIT
            }
        return json_output

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_simple_filter(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
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
        else:
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
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_date_comparison(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
            expected_filter = {
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
                    ]
                }
            }
        else:
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
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_numeric_comparison(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
            expected_filter = {
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
                    ]
                }
            }
        else:
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
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_numeric_comparison_negative(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
            expected_filter = {
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
                    ]
                }
            }
        else:
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
                                        "lte": -100.32,
                                    }
                                }
                            }
                        }
                    }
                }
            }
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_numeric_equality_negative(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
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
        else:
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
                                            "case_properties.key.exact": "number"
                                        }
                                    },
                                    {
                                        "term": {
                                            "case_properties.value.exact": -100.32,
                                        }
                                    }
                                )
                            }
                        }
                    }
                }
            }
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_case_property_existence(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
            # ES7: NOT (NOT property is set OR property  == "")
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
        else:
            # ES2: property is set AND NOT property == ""
            expected_filter = {
                "and": (
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
                                        "term": {
                                            "case_properties.key.exact": "property"
                                        }
                                    }
                                }
                            }
                        }
                    },
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
                    }
                )
            }
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py", 1)
    def test_nested_filter1(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
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
                    ]
                }
            }
        else:
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
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_parent_lookups(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
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
                                                    "indices.referenced_id": ["self.parent_case_id"]
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
        else:
            expected_filter = {
                "nested": {
                    "path": "indices",
                    "query": {
                        "filtered": {
                            "query": {
                                "match_all": {
                                },
                            },
                            "filter": {
                                "and": (
                                    {
                                        "terms": {
                                            "indices.referenced_id": ["self.parent_case_id"],
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
                    }
                }
            }
        return expected_filter

    @check_query("corehq/apps/case_search/tests/test_filter_dsl.py")
    def test_nested_parent_lookups(self):
        def convert(expected_filter):
            expected_filter = convert_to_es2(expected_filter)
            return expected_filter
        if self.select == "convert":
            return convert
        if self.is_es7():
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
                                                    "indices.referenced_id": ["self.parent_case_id"]
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
        else:
            expected_filter = {
                "nested": {
                    "path": "indices",
                    "query": {
                        "filtered": {
                            "query": {
                                "match_all": {
                                },
                            },
                            "filter": {
                                "and": (
                                    {
                                        "terms": {
                                            "indices.referenced_id": ["self.parent_case_id"],
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
                    }
                }
            }
        return expected_filter

    @check_query("corehq/apps/ota/tests/test_search_claim_endpoints.py")
    def test_add_blacklisted_ids(self):
        def convert(expected):
            expected = convert_to_es2(expected)
            return expected
        if self.select == "convert":
            return convert
        if self.is_es7():
            expected = {
                "query": {
                    "bool": {
                        "filter": [
                            {'term': {'domain.exact': 'swashbucklers'}},
                            {"term": {"type.exact": "case_type"}},
                            {"term": {"closed": False}},
                            {
                                "bool": {
                                    "must_not": {
                                        "term": {
                                            "owner_id": "id1"
                                        }
                                    }
                                }
                            },
                            {
                                "bool": {
                                    "must_not": {
                                        "term": {
                                            "owner_id": "id2"
                                        }
                                    }
                                }
                            },
                            {
                                "bool": {
                                    "must_not": {
                                        "term": {
                                            "owner_id": "id3,id4"
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
                "size": CASE_SEARCH_MAX_RESULTS
            }
        else:
            expected = {'query':
                        {'filtered':
                        {'filter':
                        {'and': [
                            {'term': {'domain.exact': 'swashbucklers'}},
                            {"term": {"type.exact": "case_type"}},
                            {"term": {"closed": False}},
                            {'not': {'term': {'owner_id': 'id1'}}},
                            {'not': {'term': {'owner_id': 'id2'}}},
                            {'not': {'term': {'owner_id': 'id3,id4'}}},
                            {'match_all': {}}
                        ]},
                        "query": {
                            "match_all": {}
                        }}},
                        'size': CASE_SEARCH_MAX_RESULTS}
        return expected

    @check_query("corehq/apps/ota/tests/test_search_claim_endpoints.py")
    def test_add_ignore_pattern_queries(self):
        def convert(expected):
            expected = convert_to_es2(expected)
            return expected
        if self.select == "convert":
            return convert
        if self.is_es7():
            expected = {
                "query": {
                    "bool": {
                        "filter": [
                            {'term': {'domain.exact': 'swashbucklers'}},
                            {"term": {"type.exact": "case_type"}},
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
                                                                            "case_properties.value.exact": "this should be"
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
                                                                            "case_properties.value.exact": "this word should not be gone"
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
                "size": CASE_SEARCH_MAX_RESULTS
            }
        else:
            expected = {"query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                "term": {
                                    "domain.exact": "swashbucklers"
                                }
                            },
                            {
                                "term": {
                                    "type.exact": "case_type"
                                }
                            },
                            {
                                "term": {
                                    "closed": False
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
                                                                "case_properties.key.exact": "phone_number"
                                                            }
                                                        },
                                                        {
                                                            "term": {
                                                                "case_properties.value.exact": "91999"
                                                            }
                                                        }
                                                    ),
                                                },
                                                "query": {
                                                    "match_all": {
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
                                                    "and": (
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
                                                    )
                                                },
                                                "query": {
                                                    "match_all": {
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
                                                    "and": (
                                                        {
                                                            "term": {
                                                                "case_properties.key.exact": "name"
                                                            }
                                                        },
                                                        {
                                                            "term": {
                                                                "case_properties.value.exact": "this should be"
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
                                },
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "filtered": {
                                                "filter": {
                                                    "and": (
                                                        {
                                                            "term": {
                                                                "case_properties.key.exact": "other_name"
                                                            }
                                                        },
                                                        {
                                                            "term": {
                                                                "case_properties.value.exact": (
                                                                    "this word should not be gone"
                                                                )
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
                            ]
                        }
                    }
                }
            },
                "size": CASE_SEARCH_MAX_RESULTS,
            }
        return expected

    @check_query("corehq/apps/api/tests/form_resources.py")
    def test_get_list_archived(self):
        def convert(expected):
            expected = convert_to_es2(expected)
            return expected
        if self.select == "convert":
            return convert
        if self.is_es7():
            expected = [
                {
                    "term": {
                        "domain.exact": "qwerty"
                    }
                },
                {
                    "bool": {
                        "should": [
                            {"term": {"doc_type": "xforminstance"}},
                            {"term": {"doc_type": "xformarchived"}}
                        ]
                    }
                },
                {
                    "match_all": {}
                }
            ]
        else:
            expected = [
                {'term': {'domain.exact': 'qwerty'}},
                {'or': (
                    {'term': {'doc_type': 'xforminstance'}},
                    {'term': {'doc_type': 'xformarchived'}}
                )},
                {'match_all': {}}
            ]
        return expected


if __name__ == "__main__":
    main()
