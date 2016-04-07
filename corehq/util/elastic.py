from django.conf import settings
from elasticsearch import NotFoundError

from corehq.util.test_utils import unit_testing_only

TEST_ES_PREFIX = 'test_'


def es_index(index):
    prefix = '' if not settings.UNIT_TESTING else TEST_ES_PREFIX
    return "{}{}".format(prefix, index)


@unit_testing_only
def ensure_index_deleted(es_index):
    ensure_production_index_deleted(es_index)


def ensure_production_index_deleted(es_index):
    """
    Like ensure_index_deleted but usable outside unit tests
    """
    try:
        delete_production_es_index(es_index)
    except NotFoundError:
        pass


@unit_testing_only
def delete_es_index(es_index):
    if es_index.startswith(TEST_ES_PREFIX):
        delete_production_es_index(es_index)

    else:
        raise DeleteProductionESIndex('You cannot delete a production index in tests!!')


def delete_production_es_index(es_index):
    """
    Like delete_es_index but usable outside unit tests
    """
    from corehq.elastic import get_es_new
    es = get_es_new()
    es.indices.delete(index=es_index)


class DeleteProductionESIndex(Exception):
    pass
