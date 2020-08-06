from pprint import pformat
from corehq.apps.es.tests.utils import convert_to_es2


def eq(actual, expected, path=""):
    if actual == expected:
        return
    if isinstance(actual, dict) and isinstance(expected, dict):
        if actual.keys() == expected.keys():
            for key, a_val in actual.items():
                eq(a_val, expected[key], f"{path}.{key}" if path else key)
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) == len(expected):
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
    queries = list(Queries())
    print(f"checking {len(queries)} methods...")
    for name, es2_query, es7_query, convert in queries:
        print(name)
        eq(convert(es7_query), es2_query)


SIZE_LIMIT = 1000000


class Queries:
    def is_es7(self):
        return self.select == "es7"

    def __iter__(self):
        def query_methods():
            for name in dir(self):
                if name == "is_es7":
                    continue
                method = getattr(self, name)
                if callable(method) and not name.startswith("__"):
                    yield name, method

        def lineno(pair):
            return pair[1].__func__.__code__.co_firstlineno

        for name, method in sorted(query_methods(), key=lineno):
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
            yield name, es2_query, es7_query, convert

    # test_aggregations.py
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

    # test_case_search_es.py
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

    # test_case_search_es.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_esquery.py
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

    # test_filters.py
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

    # test_filters.py
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

    # test_filters.py
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

    # test_filters.py
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

    # test_filters.py
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

    # test_sms.py
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
