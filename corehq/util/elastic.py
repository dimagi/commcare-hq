from django.conf import settings
from corehq.util.es.elasticsearch import NotFoundError

from corehq.util.test_utils import unit_testing_only, trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping

TEST_ES_PREFIX = 'test_'


def es_index(index):
    prefix = '' if not settings.UNIT_TESTING else TEST_ES_PREFIX
    return "{}{}".format(prefix, index)


@unit_testing_only
def reset_es_index(index_info):
    with trap_extra_setup(ConnectionError):
        from corehq.elastic import get_es_new
        ensure_index_deleted(index_info.index)
        initialize_index_and_mapping(get_es_new(), index_info)


@unit_testing_only
def ensure_index_deleted(es_index):
    try:
        delete_es_index(es_index)
    except NotFoundError:
        pass


@unit_testing_only
def delete_es_index(es_index):
    if es_index.startswith(TEST_ES_PREFIX):
        from corehq.elastic import get_es_new
        es = get_es_new()
        es.indices.delete(index=es_index)
    else:
        raise DeleteProductionESIndex('You cannot delete a production index in tests!!')


class DeleteProductionESIndex(Exception):
    pass
