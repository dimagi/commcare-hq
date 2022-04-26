import json
from contextlib import contextmanager
from functools import wraps
from datetime import datetime
from inspect import isclass

from nose.plugins.attrib import attr
from nose.tools import nottest

from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.tests.utils import TEST_INDEX_INFO

from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup

from ..client import ElasticDocumentAdapter, ElasticManageAdapter
from ..registry import (
    register,
    deregister,
    registry_entry,
)

TEST_ES_MAPPING = {
    '_meta': {
        'comment': 'Bare bones index for ES testing',
        'created': datetime.isoformat(datetime.utcnow()),
    },
    "properties": {
        "doc_type": {
            "index": "not_analyzed", "type": "string"
        },
    }
}
TEST_ES_TYPE = 'test_es_doc'
TEST_ES_ALIAS = "test_es"


es_test_attr = attr(es_test=True)


class TEST_ES_INFO:
    alias = TEST_ES_ALIAS
    type = TEST_ES_TYPE


class ElasticTestMixin(object):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._es_instance = get_es_new()
        initialize_index_and_mapping(cls._es_instance, TEST_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(TEST_INDEX_INFO.index)
        super().tearDownClass()

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
def es_test(test=None, index=None, indices=[], setup_class=False):
    """Decorator for Elasticsearch tests.
    The decorator sets the `es_test` nose attribute and optionally performs
    index registry setup/teardown before and after the test(s).

    :param test: A test class, method, or function (only used via the @decorator
                 syntax).
    :param index: Index info object or `(info_obj, cname)` tuple of an index to
                  be registered for the test, mutually exclusive with the
                  `indices` param (raises ValueError if both provided).
    :param indices: A list of index info objects (or tuples, see above) of
                    indices to be registered for the test, mutually exclusive
                    with the the `index` param (raises ValueError).
    :param setup_class: Set to `True` to perform registry setup/teardown in the
                        `setUpClass` and `tearDownClass` (instead of the default
                        `setUp` and `tearDown`) methods. Invalid if true when
                        decorating non-class objects (raises ValueError).
    :raises: ValueError

    See test_test_utils.py for examples.
    """
    if test is None:
        def es_test_decorator(test):
            return es_test(test, index, indices, setup_class)
        return es_test_decorator

    if not (index or indices):
        return es_test_attr(test)

    if index is None:
        _registration_info = list(indices)
    elif not indices:
        _registration_info = [index]
    else:
        raise ValueError(f"index and indices are mutually exclusive {(index, indices)}")

    def registry_setup():
        reg = {}
        for info in _registration_info:
            if isinstance(info, tuple):
                info, cname = info
            else:
                cname = None
            reg[register(info, cname)] = info
        return reg

    def registry_teardown():
        for dereg in _registration_info:
            if isinstance(dereg, tuple):
                info, dereg = dereg
            deregister(dereg)

    if isclass(test):
        test = _add_setup_and_teardown(test, setup_class, registry_setup, registry_teardown)
    else:
        if setup_class:
            raise ValueError(f"keyword 'setup_class' is for class decorators, test={test}")
        test = _decorate_test_function(test, registry_setup, registry_teardown)
    return es_test_attr(test)


def _decorate_test_function(test, registry_setup, registry_teardown):

    @wraps(test)
    def wrapper(*args, **kw):
        registry_setup()
        try:
            return test(*args, **kw)
        finally:
            registry_teardown()

    return wrapper


def _add_setup_and_teardown(test_class, setup_class, registry_setup, registry_teardown):

    def setup_decorator(setup):
        @wraps(setup)
        def wrapper(self, *args, **kw):
            self._indices = registry_setup()
            if setup is not None:
                return setup(self, *args, **kw)
        return wrapper

    def teardown_decorator(teardown):
        @wraps(teardown)
        def wrapper(*args, **kw):
            try:
                if teardown is not None:
                    return teardown(*args, **kw)
            finally:
                registry_teardown()
        return wrapper

    def decorate(name, decorator):
        func_name = f"{name}Class" if setup_class else name
        func = getattr(test_class, func_name, None)
        if setup_class:
            if func is not None:
                try:
                    func = func.__func__
                except AttributeError:
                    raise ValueError(f"'setup_class' expects a classmethod, "
                                     f"got {func} (test_class={test_class})")
            decorated = classmethod(decorator(func))
        else:
            decorated = decorator(func)
        setattr(test_class, func_name, decorated)

    decorate("setUp", setup_decorator)
    decorate("tearDown", teardown_decorator)
    return test_class


@contextmanager
def temporary_index(index, type_=None, mapping=None, *, purge=True):
    if (type_ is None and mapping is not None) or \
       (type_ is not None and mapping is None):
        raise ValueError(f"type_ and mapping args are mutually inclusive "
                         f"(index={index!r}, type_={type_!r}, "
                         f"mapping={mapping!r})")
    manager = ElasticManageAdapter()
    if purge and manager.index_exists(index):
        manager.index_delete(index)
    manager.index_create(index)
    if type_ is not None:
        manager.index_put_mapping(index, type_, mapping)
    try:
        yield
    finally:
        manager.index_delete(index)


def populate_es_index(models, index_cname, doc_prep_fn=lambda doc: doc):
    index_info = registry_entry(index_cname)
    es = get_es_new()
    with trap_extra_setup(ConnectionError):
        initialize_index_and_mapping(es, index_info)
    for model in models:
        send_to_elasticsearch(
            index_cname,
            doc_prep_fn(model.to_json() if hasattr(model, 'to_json') else model)
        )
    es.indices.refresh(index_info.index)


def populate_user_index(users):
    populate_es_index(users, 'users')


def case_search_es_setup(domain, case_blocks):
    """Submits caseblocks, creating the cases, then sends them to ES"""
    from corehq.apps.hqcase.utils import submit_case_blocks
    xform, cases = submit_case_blocks([cb.as_text() for cb in case_blocks], domain=domain)
    assert not xform.is_error, xform
    order = {cb.case_id: index for index, cb in enumerate(case_blocks)}
    # send cases to ES in the same order they were passed in so `indexed_on`
    # order is predictable for TestCaseListAPI.test_pagination and others
    cases = sorted(cases, key=lambda case: order[case.case_id])
    populate_es_index(cases, 'case_search', transform_case_for_elasticsearch)


def case_search_es_teardown():
    FormProcessorTestUtils.delete_all_cases()
    ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)


def docs_from_result(result):
    """Convenience function for extracting the documents (without the search
    metadata) from an Elastic results object.

    :param result: ``dict`` search results object
    :returns: ``[<doc>, ...]`` list
    """
    return [h["_source"] for h in result["hits"]["hits"]]


def docs_to_dict(docs):
    """Convenience function for getting a ``dict`` of documents keyed by their
    ID for testing unordered equality (or other reasons it might be desireable).

    :param docs: iterable of documents in the "json" (``dict``) format
    :returns: ``{<doc_id>: <doc_sans_id>, ...}`` dict
    """
    docs_dict = {}
    for full_doc in docs:
        doc = full_doc.copy()
        doc_id = doc.pop("_id")
        # Ensure we never get multiple docs with the same ID (important
        # because putting them in a dict like we're doing here would destroy
        # information about the original collection of documents in such a case).
        # Don't use 'assert' here (makes test failures VERY confusing).
        if doc_id in docs_dict:
            raise ValueError(f"doc ID {doc_id!r} already exists: {docs_dict}")
        docs_dict[doc_id] = doc
    return docs_dict


@nottest
class TestDoc:
    """A test "model" class for performing generic document and index tests."""

    def __init__(self, id=None, value=None):
        self.id = id
        self.value = value

    @property
    def entropy(self):
        if self.value is None:
            return None
        return len(set(str(self.value)))

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id}, value={self.value!r}>"


@nottest
class TestDocumentAdapter(ElasticDocumentAdapter):
    """An ``ElasticDocumentAdapter`` implementation for Elasticsearch actions
    involving ``TestDoc`` model objects.
    """

    _index_name = "doc-adapter"
    type = "test_doc"
    mapping = {
        "properties": {
            "value": {
                "index": "not_analyzed",
                "type": "string"
            },
            "entropy": {
                "type": "integer"
            },
        }
    }

    @classmethod
    def from_python(cls, doc):
        return doc.id, {"value": doc.value, "entropy": doc.entropy}
