from dimagi.ext import jsonobject
from copy import copy
from datetime import datetime
from elasticsearch import TransportError
from pillowtop import get_all_pillow_classes
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


class ElasticsearchIndexInfo(jsonobject.JsonObject):
    index = jsonobject.StringProperty(required=True)
    alias = jsonobject.StringProperty()
    type = jsonobject.StringProperty()
    meta = jsonobject.DictProperty()
    mapping = jsonobject.DictProperty()

    def __unicode__(self):
        return u'{} ({})'.format(self.alias, self.index)


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
    return initialize_index_and_mapping(pillow.get_es_new(), get_index_info_from_pillow(pillow))


def initialize_index_and_mapping(es, index_info):
    index_exists = es.indices.exists(index_info.index)
    if not index_exists:
        initialize_index(es, index_info)
    initialize_mapping_if_necessary(es, index_info)


def initialize_index(es, index_info):
    return create_index_and_set_settings_normal(es, index_info.index, index_info.meta)


def mapping_exists(es, index_info):
    try:
        return es.indices.get_mapping(index_info.index, index_info.type)
    except TransportError:
        return {}


def initialize_mapping_if_necessary(es, index_info):
    """
    Initializes the elasticsearch mapping for this pillow if it is not found.
    """
    if not mapping_exists(es, index_info):
        pillow_logging.info("Initializing elasticsearch mapping for [%s]" % index_info.type)
        mapping = copy(index_info.mapping)
        mapping['_meta']['created'] = datetime.isoformat(datetime.utcnow())
        mapping_res = es.indices.put_mapping(index_info.type, {index_info.type: mapping}, index=index_info.index)
        if mapping_res.get('ok', False) and mapping_res.get('acknowledged', False):
            # API confirms OK, trust it.
            pillow_logging.info("Mapping set: [%s] %s" % (index_info.type, mapping_res))
    else:
        pillow_logging.info("Elasticsearch mapping for [%s] was already present." % index_info.type)


def assume_alias_for_pillow(pillow):
    """
    Assigns the pillow's `es_alias` to its index in elasticsearch.

    This operation removes the alias from any other indices it might be assigned to
    """
    assume_alias(pillow.get_es_new(), pillow.es_index, pillow.es_alias)


def assume_alias(es, index, alias):
    """
    This operation assigns the alias to the index and removes the alias
    from any other indices it might be assigned to.
    """
    if es.indices.exists_alias(None, alias):
        # this part removes the conflicting aliases
        alias_indices = es.indices.get_alias(alias).keys()
        for aliased_index in alias_indices:
            es.indices.delete_alias(aliased_index, alias)
    es.indices.put_alias(index, alias)


def doc_exists(pillow, doc_id_or_dict):
    """
    Check if a document exists, by ID or the whole document.
    """
    if isinstance(doc_id_or_dict, basestring):
        doc_id = doc_id_or_dict
    else:
        assert isinstance(doc_id_or_dict, dict)
        doc_id = doc_id_or_dict['_id']
    return pillow.get_es_new().exists(pillow.es_index, pillow.es_type, doc_id)


def get_all_elasticsearch_pillow_classes():
    from pillowtop.listener import AliasedElasticPillow
    return filter(lambda x: issubclass(x, AliasedElasticPillow), get_all_pillow_classes())


def get_all_inferred_es_indices_from_pillows():
    """
    Get all expected elasticsearch indices according to the currently running code
    """
    seen_indices = set()
    seen_aliases = set()
    pillows = get_all_elasticsearch_pillow_classes()
    for pillow in pillows:
        assert pillow.es_index not in seen_indices
        assert pillow.es_alias not in seen_aliases
        yield get_index_info_from_pillow(pillow)
        seen_indices.add(pillow.es_index)
        seen_aliases.add(pillow.es_alias)


def get_index_info_from_pillow(pillow):
    return ElasticsearchIndexInfo(
        index=pillow.es_index,
        alias=pillow.es_alias,
        type=pillow.es_type,
        meta=pillow.es_meta,
        mapping=pillow.default_mapping,
    )
