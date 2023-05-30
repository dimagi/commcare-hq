from django.conf import settings
from corehq.util.es.elasticsearch import NotFoundError
from corehq.apps.es.client import manager

from corehq.util.test_utils import unit_testing_only
from unittest import SkipTest

TEST_ES_PREFIX = 'test_'


def prefix_for_tests(index):
    prefix = '' if not settings.UNIT_TESTING else TEST_ES_PREFIX
    return "{}{}".format(prefix, index)


@unit_testing_only
def ensure_index_deleted(es_index):
    try:
        delete_es_index(es_index)
    except NotFoundError:
        pass


@unit_testing_only
def delete_es_index(es_index):
    if es_index.startswith(TEST_ES_PREFIX):
        manager.index_delete(es_index)
    else:
        raise DeleteProductionESIndex('You cannot delete a production index in tests!!')


@unit_testing_only
def ensure_active_es():
    """Only return an ES instance if it is connectable"""
    from corehq.elastic import get_es_new
    es = get_es_new()
    if not es.ping():
        raise SkipTest('Cannot connect to Elasticsearch')

    return es


class DeleteProductionESIndex(Exception):
    pass
