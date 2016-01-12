import functools
import sys
from select import select

from django.conf import settings
from elasticsearch import TransportError
from nose.tools import nottest
from unittest.case import SkipTest

TESTS_ALLOWED = None


@nottest
def require_explicit_elasticsearch_testing(fn):
    """
    This decorator is here to make it hard for developers to delete their real elasticsearch
    indices.
    """
    @functools.wraps(fn)
    def decorated(*args, **kwargs):
        assert settings.UNIT_TESTING, 'You can only run this function in unit testing mode.'
        global TESTS_ALLOWED
        if TESTS_ALLOWED is None:
            TESTS_ALLOWED = getattr(settings, 'ALLOW_ELASTICSEARCH_TESTS', None)
            if TESTS_ALLOWED is None:
                should_proceed = timed_raw_input(
                    'NOTE: set ALLOW_ELASTICSEARCH_TESTS in your localsettings '
                    'to disable this warning.\n'
                    'Are you sure you want to run ElasticSearch tests? '
                    'These may WIPE all the REAL indices on your computer? (y/n)\n',
                    default=None,
                    timeout=30,
                    stdout=sys.__stdout__,  # because nose hides sys.stdout
                )
                if should_proceed is None:
                    sys.__stdout__.write("\nTimed out. Assuming not allowed.\n")
                    should_proceed = 'n'
                TESTS_ALLOWED = should_proceed.lower().strip() == 'y'
        if not TESTS_ALLOWED:
            raise SkipTest("ElasticSearch tests not allowed")
        return fn(*args, **kwargs)
    return decorated


def get_doc_count(es, index, refresh_first=True):
    if refresh_first:
        # we default to calling refresh since ES might have stale data
        es.indices.refresh(index)
    stats = es.indices.stats(index)
    return stats['indices'][index]['total']['docs']['count']


def get_index_mapping(es, index, doc_type):
    def _format_mapping_for_es_version(mapping):
        if settings.ELASTICSEARCH_VERSION < 1.0:
            return mapping[doc_type]
        else:
            return mapping[index]['mappings'][doc_type]
    try:
        return _format_mapping_for_es_version(es.indices.get_mapping(index, doc_type))
    except TransportError:
        return {}


def timed_raw_input(prompt, timeout=None, default="", stdout=sys.stdout):
    # http://stackoverflow.com/a/3471853/10840
    # does not work on Windows
    timeout_arg = () if timeout is None else (timeout,)
    stdout.write(prompt)
    rlist, _, _ = select([sys.stdin], [], [], *timeout_arg)
    if rlist:
        return sys.stdin.readline()
    return default
