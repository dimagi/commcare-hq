from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime

from pillowtop.es_utils import (
    set_index_normal_settings,
    set_index_reindex_settings,
)

from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.pillows.case_search import \
    transform_case_for_elasticsearch as old_transform
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.pillows.mappings.utils import mapping_from_json

from .const import TEST_DOMAIN_NAME, TEST_INDEX_NAME
from .fixture_data import CASES_FIXTURE


def reset_test_index():
    es = get_es_new()
    if es.indices.exists(TEST_INDEX_NAME):
        es.indices.delete(TEST_INDEX_NAME)

    meta = deepcopy(CASE_SEARCH_INDEX_INFO.meta)
    meta['mappings'] = {CASE_ES_TYPE: _get_mapping()}
    es.indices.create(index=TEST_INDEX_NAME, body=meta)
    load_case_fixtures(es)


def _get_mapping():
    # This is the mapping we can experiment with
    mapping = mapping_from_json('test_case_search_mapping.json')
    mapping['_meta']['created'] = datetime.utcnow().isoformat()
    return mapping


def load_domain(domain):
    """Load all cases from a domain into the test index"""
    es = get_es_new()
    accessor = CaseAccessors(domain)
    case_ids = accessor.get_case_ids_in_domain()
    print(f"Loading {len(case_ids)} cases from {domain}")

    with _bulk_indexing_settings(es):
        for case in accessor.iter_cases(case_ids):
            transform_and_send(es, case.to_json())


@contextmanager
def _bulk_indexing_settings(es):
    set_index_reindex_settings(es, TEST_INDEX_NAME)
    yield
    set_index_normal_settings(es, TEST_INDEX_NAME)
    es.indices.refresh(TEST_INDEX_NAME)


def transform_and_send(es, doc_dict):
    doc = transform_case_for_elasticsearch(doc_dict)
    doc_id = doc.pop('_id')  # You can't send _id directly
    es.index(TEST_INDEX_NAME, CASE_ES_TYPE, doc, id=doc_id)


def transform_case_for_elasticsearch(doc_dict):
    # This is where we'd make any just-in-time modifications in python before
    # sending cases to ES
    return old_transform(doc_dict)


def load_case_fixtures(es):
    print(f"loading fixture data into domain {TEST_DOMAIN_NAME}")
    with _bulk_indexing_settings(es):
        for case in CASES_FIXTURE:
            transform_and_send(es, case.to_json())
