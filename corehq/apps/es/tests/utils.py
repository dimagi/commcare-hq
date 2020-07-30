import functools
import inspect
import json

from django.conf import settings
from django.test import override_settings
from importlib import reload

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


def reload_modules():
    from corehq.util.es import elasticsearch
    from corehq import elastic
    from corehq.util.es import interface
    from pillowtop import es_utils
    from pillowtop.processors import elastic as pelastic
    from corehq.util import elastic as uelastic
    reload(elasticsearch)
    reload(elastic)
    reload(interface)
    reload(es_utils)
    reload(pelastic)
    reload(uelastic)


def skip_and_reload_decorator(decorator):
    @functools.wraps(decorator)
    def decorate(cls):
        if not getattr(settings, 'ELASTICSEARCH_7_PORT', False):
            setattr(cls, '__unittest_skip__', True)
            setattr(cls, '__unittest_skip_why__', 'settings.ELASTICSEARCH_7_PORT is not defined')
            return cls
        builtins = ['setUp', 'setUpClass', 'tearDown', 'tearDownClass']
        for (method_name, method) in inspect.getmembers(cls):
            if method_name in builtins or method_name.startswith("test_"):
                setattr(cls, method_name, decorator(getattr(cls, method_name)))
        return cls
    return decorate


def reload_modules_decorator(fn):
    @functools.wraps(fn)
    def wrap(*args):
        with override_settings(ELASTICSEARCH_MAJOR_VERSION=2, ELASTICSEARCH_PORT=getattr('settings', 'ELASTICSEARCH_7_PORT', 5200)):
            reload_modules()
            res = fn(*args)
        reload_modules()
        return res
    return wrap


run_on_es2 = skip_and_reload_decorator(reload_modules_decorator)
