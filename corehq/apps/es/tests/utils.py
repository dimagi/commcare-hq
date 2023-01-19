import json
from contextlib import contextmanager
from functools import wraps
from datetime import datetime
from inspect import isclass

from nose.plugins.attrib import attr
from nose.tools import nottest

from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.tests.utils import TEST_INDEX_INFO

from corehq.apps.es.client import ElasticMultiplexAdapter
from corehq.apps.es.migration_operations import CreateIndex
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.tests.util.warnings import filter_warnings
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup

from ..client import ElasticDocumentAdapter, manager
from ..transient_util import index_info_from_cname

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

ignore_index_settings_key_warning = filter_warnings(
    "ignore",
    r"Invalid index settings key .+, expected one of \[",
    UserWarning,
)

es_test_attr = attr(es_test=True)


class TEST_ES_INFO:
    alias = TEST_ES_ALIAS
    type = TEST_ES_TYPE


class ElasticTestMixin(object):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._es_instance = get_es_new()
        # TODO: make individual test[ case]s warning-safe and remove this
        with ignore_index_settings_key_warning:
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
        self.assertTrue(validation['valid'], validation)

    def checkQuery(self, query, expected_json, is_raw_query=False, validate_query=True):
        self.maxDiff = None
        if is_raw_query:
            raw_query = query
        else:
            raw_query = query.raw_query
        msg = "Expected Query:\n{}\nGenerated Query:\n{}".format(
            json.dumps(expected_json, indent=4),
            json.dumps(raw_query, indent=4),
        )
        # NOTE: This makes it [a, b, c] == [b, c, a] which shouldn't matter in ES queries
        expected_json = json.loads(json.dumps(expected_json))
        raw_query = json.loads(json.dumps(raw_query))
        self.assertEqual(raw_query, expected_json, msg=msg)
        if validate_query:
            # some queries need more setup to validate like initializing the specific index
            #   that they are querying.
            self.validate_query(raw_query)


@nottest
def es_test(test=None, requires=[], setup_class=False):
    """Decorator for Elasticsearch tests.
    The decorator sets the ``es_test`` nose attribute and optionally performs
    index setup/cleanup before and after the test(s).

    :param test: A test class, method, or function -- only used via the
        ``@decorator`` format (i.e. not the ``@decorator(...)`` format).
    :param requires: A list of document adapters whose indexes are required by
        the test(s).
    :param setup_class: Optional (default: ``False``). Set to ``True`` to
        perform index setup/add-cleanup in the ``setUpClass`` method (instead of
        ``setUp``). Invalid if true when decorating non-class objects (raises
        ValueError).
    :raises: ``ValueError``

    See test_test_utils.py for examples.
    """
    if test is None:
        def es_test_decorator(test):
            return es_test(test, requires, setup_class)
        return es_test_decorator

    if not requires:
        return es_test_attr(test)

    def setup_func():
        comment = f"created for {test.__module__}.{test.__qualname__}"
        for adapter in iter_all_doc_adapters():
            setup_test_index(adapter, comment)

    def cleanup_func():
        for adapter in iter_all_doc_adapters():
            cleanup_test_index(adapter)

    def iter_all_doc_adapters():
        for adapter in adapters:
            if isinstance(adapter, ElasticMultiplexAdapter):
                yield adapter.primary
                yield adapter.secondary
            else:
                yield adapter

    adapters = list(requires)
    if isclass(test):
        test = _add_setup_and_cleanup(test, setup_class, setup_func, cleanup_func)
    else:
        if setup_class:
            raise ValueError(f"keyword 'setup_class' is for class decorators, test={test}")
        test = _decorate_test_function(test, setup_func, cleanup_func)
    return es_test_attr(test)


def _decorate_test_function(test, setup_func, cleanup_func):

    @wraps(test)
    def wrapper(*args, **kw):
        setup_func()
        try:
            return test(*args, **kw)
        finally:
            cleanup_func()

    return wrapper


def _add_setup_and_cleanup(test_class, setup_class, setup_func, cleanup_func):
    """Decorates ``test_class.setUp[Class]`` to call ``setup_func()`` and
    ``test_class.add[Class]Cleanup(cleanup_func)``.

    :param test_class: the test case class being decorated
    :param setup_class: whether or not the *class* methods (e.g.
        ``setUpClass()`` and ``addClassCleanup()``) should be used.
    :param setup_func: a callable that performs the Elastic index setup
    :param cleanup_func: a callable that tears down what ``setup_func`` did
    """

    def setup_decorator(setup):
        @wraps(setup)
        def wrapper(self, *args, **kw):
            if setup_class:
                cleanup_args = (cleanup_func,)
                cleanup_meth = "addClassCleanup"
            else:
                cleanup_args = (self, cleanup_func)
                cleanup_meth = "addCleanup"
            setup_func()
            getattr(test_class, cleanup_meth)(*cleanup_args)
            if setup is not None:
                # call the existing 'setUp[Class]()' method
                return setup(self, *args, **kw)
        return wrapper

    func_name = "setUpClass" if setup_class else "setUp"
    func = getattr(test_class, func_name, None)
    if setup_class:
        # decorate setUpClass
        if func is not None:
            # 'func' is the classmethod decoration, get the function it wraps
            try:
                func = func.__func__
            except AttributeError:
                raise ValueError(f"'setup_class' expects a classmethod, "
                                 f"got {func} (test_class={test_class})")
        decorated = classmethod(setup_decorator(func))
    else:
        # decorate setUp
        decorated = setup_decorator(func)
    setattr(test_class, func_name, decorated)
    return test_class


@nottest
def setup_test_index(adapter, comment):
    CreateIndex(
        adapter.index_name,
        adapter.type,
        adapter.mapping,
        adapter.analysis,
        adapter.settings_key,
        comment=comment,
    ).run()


@nottest
def cleanup_test_index(adapter):
    manager.index_delete(adapter.index_name)


@contextmanager
def temporary_index(index, type_=None, mapping=None, *, purge=True):
    if (type_ is None and mapping is not None) or \
       (type_ is not None and mapping is None):
        raise ValueError(f"type_ and mapping args are mutually inclusive "
                         f"(index={index!r}, type_={type_!r}, "
                         f"mapping={mapping!r})")
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
    index_info = index_info_from_cname(index_cname)
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
    populate_case_search_index(cases)


def populate_case_search_index(cases):
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


test_adapter = TestDocumentAdapter("doc-adapter", "test_doc")
