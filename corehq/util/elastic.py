from django.conf import settings
from corehq.util.es.elasticsearch import NotFoundError

from corehq.util.test_utils import unit_testing_only, trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping

TEST_ES_PREFIX = 'test_'


def prefix_for_tests(index):
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
        try:
            es.indices.delete(index=es_index)
        except NotFoundError:
            from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
            # could be ILM index
            if es_index == XFORM_INDEX_INFO.index:
                cleanup_ilm_index(es, XFORM_INDEX_INFO)
    else:
        raise DeleteProductionESIndex('You cannot delete a production index in tests!!')


def cleanup_ilm_index(es, index_info):
    if index_info.is_ilm_index:
        es.indices.delete(index=index_info.index + "*")
        es.ilm.delete_lifecycle(index_info.ilm_config)
        es.indices.delete_index_template(index_info.ilm_template_name)


class DeleteProductionESIndex(Exception):
    pass
