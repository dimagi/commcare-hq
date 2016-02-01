from collections import namedtuple
from copy import copy
from datetime import datetime
from elasticsearch import TransportError
from pillowtop.logger import pillow_logging

INDEX_REINDEX_SETTINGS = {
    "index": {
        "refresh_interval": "900s",
        "merge.policy.merge_factor": 20,
        "store.throttle.max_bytes_per_sec": "1mb",
        "store.throttle.type": "merge",
        "number_of_replicas": "0"
    }
}

INDEX_STANDARD_SETTINGS = {
    "index": {
        "refresh_interval": "1s",
        "merge.policy.merge_factor": 10,
        "store.throttle.max_bytes_per_sec": "5mb",
        "store.throttle.type": "node",
        "number_of_replicas": "0"
    }
}


ElasticsearchIndexMeta = namedtuple('ElasticsearchIndexMeta', ['index', 'type'])


def update_settings(es, index, settings_dict):
    return es.indices.put_settings(settings_dict, index=index)


def set_index_reindex_settings(es, index):
    """
    Set a more optimized setting setup for fast reindexing
    """
    return update_settings(es, index, INDEX_REINDEX_SETTINGS)


def set_index_normal_settings(es, index):
    """
    Normal indexing configuration
    """
    return update_settings(es, index, INDEX_STANDARD_SETTINGS)


def create_index_and_set_settings_normal(es, index, metadata=None):
    metadata = metadata or {}
    es.indices.create(index=index, body=metadata)
    set_index_normal_settings(es, index)


def completely_initialize_pillow_index(pillow):
    """
    This utility can be used to initialize the elastic index and mapping for a pillow
    """
    index_exists = pillow_index_exists(pillow)
    if not index_exists:
        create_index_for_pillow(pillow)
    pillow_logging.info("Pillowtop [%s] Initializing mapping in ES" % pillow.get_name())
    initialize_mapping_if_necessary(pillow)


def pillow_index_exists(pillow):
    return pillow.get_es_new().indices.exists(pillow.es_index)


def create_index_for_pillow(pillow):
    return create_index_and_set_settings_normal(pillow.get_es_new(), pillow.es_index, pillow.es_meta)


def pillow_mapping_exists(pillow):
    try:
        return pillow.get_es_new().indices.get_mapping(pillow.es_index, pillow.es_type)
    except TransportError:
        return {}


def initialize_mapping_if_necessary(pillow):
    """
    Initializes the elasticsearch mapping for this pillow if it is not found.
    """
    es = pillow.get_es_new()
    if not pillow_mapping_exists(pillow):
        pillow_logging.info("Initializing elasticsearch mapping for [%s]" % pillow.es_type)
        mapping = copy(pillow.default_mapping)
        mapping['_meta']['created'] = datetime.isoformat(datetime.utcnow())
        mapping_res = es.indices.put_mapping(pillow.es_index, pillow.es_type, {pillow.es_type: mapping})
        if mapping_res.get('ok', False) and mapping_res.get('acknowledged', False):
            # API confirms OK, trust it.
            pillow_logging.info("Mapping set: [%s] %s" % (pillow.es_type, mapping_res))
    else:
        pillow_logging.info("Elasticsearch mapping for [%s] was already present." % pillow.es_type)


def assume_alias_for_pillow(pillow):
    """
    Assigns the pillow's `es_alias` to its index in elasticsearch.

    This operation removes the alias from any other indices it might be assigned to
    """
    es_new = pillow.get_es_new()
    if es_new.indices.exists_alias(pillow.es_alias):
        # this part removes the conflicting aliases
        alias_indices = es_new.indices.get_alias(pillow.es_alias).keys()
        for aliased_index in alias_indices:
            es_new.indices.delete_alias(aliased_index, pillow.es_alias)

    es_new.indices.put_alias(pillow.es_index, pillow.es_alias)


def doc_exists(pillow, doc_id_or_dict):
    """
    Check if a document exists, by ID or the whole document.
    """
    if isinstance(doc_id_or_dict, basestring):
        doc_id = doc_id_or_dict
    else:
        assert isinstance(doc_id_or_dict, dict)
        doc_id = doc_id_or_dict['_id']
    return pillow.get_es_new().exists(pillow.es_index, doc_id, pillow.es_type)
