import json
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
        validation = self._es_instance.indices.validate_query(body=query, index=TEST_INDEX_INFO.index, params={'explain': 'true'})
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
        test = _decorate_es_methods(test, setup_class, registry_setup, registry_teardown)
    else:
        if setup_class:
            raise ValueError(f"keyword 'setup_class' is for class decorators, test={test}")
        test = _decorate_es_function(test, registry_setup, registry_teardown)
    return es_test_attr(test)


def _decorate_es_function(test, registry_setup, registry_teardown):

    @wraps(test)
    def wrapper(*args, **kw):
        registry_setup()
        try:
            return test(*args, **kw)
        finally:
            registry_teardown()

    return wrapper


def _decorate_es_methods(test, setup_class, registry_setup, registry_teardown):

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
        func = getattr(test, func_name, None)
        if setup_class:
            if func is not None:
                try:
                    func = func.__func__
                except AttributeError:
                    raise ValueError(f"'setup_class' expects a classmethod, got {func} (test={test})")
            decorated = classmethod(decorator(func))
        else:
            decorated = decorator(func)
        setattr(test, func_name, decorated)

    decorate("setUp", setup_decorator)
    decorate("tearDown", teardown_decorator)
    return test


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
