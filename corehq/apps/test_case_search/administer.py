from copy import deepcopy
from datetime import datetime

from pillowtop.es_utils import (
    set_index_normal_settings,
    set_index_reindex_settings,
)

from corehq.elastic import get_es_new
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.pillows.mappings.utils import mapping_from_json

from .const import TEST_INDEX_NAME


def reset_test_index():
    print("resetting")
    es = get_es_new()
    _delete_and_recreate_index(es)

    set_index_reindex_settings(es, TEST_INDEX_NAME)

    set_index_normal_settings(es, TEST_INDEX_NAME)
    es.indices.refresh(TEST_INDEX_NAME)


def _delete_and_recreate_index(es):
    if es.indices.exists(TEST_INDEX_NAME):
        es.indices.delete(TEST_INDEX_NAME)

    meta = deepcopy(CASE_SEARCH_INDEX_INFO.meta)
    meta['mappings'] = {CASE_ES_TYPE: _get_mapping()}
    es.indices.create(index=TEST_INDEX_NAME, body=meta)


def _get_mapping():
    mapping = mapping_from_json('test_case_search_mapping.json')
    mapping['_meta']['created'] = datetime.utcnow().isoformat()
    return mapping
