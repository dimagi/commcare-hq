import json
from nose.plugins.attrib import attr
from nose.tools import nottest

from corehq.elastic import get_es_new
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.tests.utils import TEST_INDEX_INFO


class ElasticTestMixin(object):

    @classmethod
    def setUpClass(cls):
        cls._es_instance = get_es_new()
        initialize_index_and_mapping(cls._es_instance, TEST_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(TEST_INDEX_INFO.index)

    def validate_query(self, query):
        if 'query' not in query:
            return
        # only query portion can be validated using ES validate API
        query = {'query': query.pop('query', {})}
        validation = self._es_instance.indices.validate_query(
            body=query,
            index=TEST_INDEX_INFO.index,
            params={'explain': 'true'},
        )
        self.assertTrue(validation['valid'])

    def checkQuery(self, query, json_output, is_raw_query=False, validate_query=True):
        self.maxDiff = None
        if is_raw_query:
            raw_query = query
        else:
            raw_query = query.raw_query
        msg = "Expected Query:\n{}\nGenerated Query:\n{}".format(
            json.dumps(json_output, indent=4),
            json.dumps(raw_query, indent=4),
        )
        # NOTE: This makes it [a, b, c] == [b, c, a] which shouldn't matter in ES queries
        json_output = json.loads(json.dumps(json_output))
        raw_query = json.loads(json.dumps(raw_query))
        self.assertEqual(raw_query, json_output, msg=msg)
        if validate_query:
            # some queries need more setup to validate like initializing the specific index
            #   that they are querying.
            self.validate_query(raw_query)


@nottest
def es_test(test):
    """Decorator for tagging ElasticSearch tests

    :param test: A test class, method, or function.
    """
    return attr(es_test=True)(test)


def convert_to_es2(es7_query):
    """Convert ES7 query to ES2 format

    :param es7_query: The query to convert.
    :returns: ES2-formatted query.
    """
    if isinstance(es7_query, dict):
        return dict(_es2_item(*x) for x in es7_query.items())
    elif isinstance(es7_query, list):
        return [convert_to_es2(x) for x in es7_query]
    elif isinstance(es7_query, tuple):
        return tuple(convert_to_es2(x) for x in es7_query)
    assert isinstance(es7_query, (str, int, float)), es7_query
    return es7_query


def _es2_item(key, value):
    if key == "must" and isinstance(value, dict):
        return "query", convert_to_es2(value)
    if key == "query":
        if _haspath(value, "bool:1.filter:1.range:1"):
            return "filter", convert_to_es2(value["bool"]["filter"])
        if _haspath(value, "bool:1.filter"):
            return key, {"filtered": convert_to_es2(value["bool"])}
    if key == "exists":
        return "not", {"missing": value}
    if key == "filter":
        if _haspath(value, "[0]:1.term:1"):
            # filter on single-item list with one term
            return key, convert_to_es2(value[0])
        if _haspath(value, "[0]:1.bool:1.filter:1[*]"):
            return key, {"and": tuple(convert_to_es2(value[0]["bool"]["filter"]))}
        if isinstance(value, list):
            return key, {"and": convert_to_es2(value)}
    if key == "bool":
        if _haspath(value, "filter:1[0]:1.nested:1"):
            return "nested", convert_to_es2(value["filter"][0]["nested"])
        if _haspath(value, "filter:1[*]"):
            return "and", tuple(convert_to_es2(value["filter"]))
        if _haspath(value, "should:1[*]"):
            return "or", tuple(convert_to_es2(value["should"]))
        if _haspath(value, "must_not:1.bool:1.should:1[*]"):
            # NOT (x OR y) -> NOT x AND NOT y
            return "and", tuple(
                convert_to_es2({"bool": {"must_not": expr}})
                for expr in value["must_not"]["bool"]["should"]
            )
        if _haspath(value, "must_not:1.bool:1.filter:1[*]"):
            # NOT (x AND y) -> NOT x OR NOT y
            return "or", tuple(
                convert_to_es2({"bool": {"must_not": expr}})
                for expr in value["must_not"]["bool"]["filter"]
            )
        if _haspath(value, "must_not:1.bool:1.must_not:1"):
            expr = value["must_not"]["bool"]["must_not"]
            if isinstance(expr, dict) and len(expr) == 1:
                key_, val = next(iter(expr.items()))
                return key_, convert_to_es2(val)
        if _haspath(value, "must_not:1"):
            return "not", convert_to_es2(value["must_not"])
    return key, convert_to_es2(value)


def _haspath(query, path):
    """Check if query has path

    :param query: ES query.
    :param path: query element path. Terms should be dict keys,
    separated by dots, and list indices enclosed in square brackets. Any
    term may be followed by `:1` to indicate that it must be the only
    item in the collection. Example: "filter:1[0]:1.nested"
    :returns: True if query has path else false.
    """
    if not path:
        return True
    allow_many = True
    if path.startswith("["):
        # path like "[42]next_path"
        index, path = path[1:].split("]", 1)
        if index == "*":
            def check():
                rng = range(len(query))
                return all(_haspath(query[i], path) for i in rng)
        else:
            def check():
                return _haspath(query[index], path)
            index = int(index)
        if path.startswith(":1"):
            allow_many = False
            path = path[2:]
            if path.startswith("."):
                path = path[1:]
        return (
            isinstance(query, (list, tuple))
            and (allow_many or len(query) == 1)
            and (index == "*" or -1 < index < len(query))
            and check()
        )
    if "." in path:
        # path like "key.next_path"
        key, path = path.split(".", 1)
    else:
        key, path = path, ""
    if "[" in key:
        # key like "key[42]"
        key, ix = key.split("[", 1)
        path = "[" + ix + path
    if key.endswith(":1"):
        allow_many = False
        key = key[:-2]
    return (
        isinstance(query, dict)
        and (allow_many or len(query) == 1)
        and key in query
        and _haspath(query[key], path)
    )


def _set_subquery(query, path, value):
    """Set value at path in ES query

    Path example:
        query.filtered.query.bool.must[0].nested.query.filtered.filter
    """
    if path.startswith("["):
        # path like "[42]next_path"
        index, path = path[1:].split("]", 1)
        index = int(index)
        if path:
            _set_subquery(query[index], path, value)
            return
        path = index
    elif "." in path:
        # path like "key.next_path"
        key, path = path.split(".", 1)
        if "[" in key:
            # key like "key[42]"
            key, ix = key.split("[", 1)
            path = "[" + ix + path
        try:
            _set_subquery(query[key], path, value)
        except KeyError:
            raise RuntimeError(f"{key!r} missing from {query} | {path}")
        return
    query[path] = value
