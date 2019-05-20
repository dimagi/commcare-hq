from __future__ import absolute_import
from __future__ import unicode_literals

import six
from dimagi.ext import jsonobject
from django.conf import settings
from copy import copy, deepcopy
from datetime import datetime
from elasticsearch import TransportError
from pillowtop import get_all_pillow_classes
from pillowtop.logger import pillow_logging

INDEX_REINDEX_SETTINGS = {
    "index": {
        "refresh_interval": "1800s",
        "merge.policy.merge_factor": 20,
        "store.throttle.max_bytes_per_sec": "1mb",
        "store.throttle.type": "merge",
    }
}

INDEX_STANDARD_SETTINGS = {
    "index": {
        "refresh_interval": "5s",
        "merge.policy.merge_factor": 10,
        "store.throttle.max_bytes_per_sec": "5mb",
        "store.throttle.type": "node",
    }
}


def _get_analysis(*names):
    return {
        "analyzer": {name: ANALYZERS[name] for name in names}
    }


ANALYZERS = {
    "default": {
        "type": "custom",
        "tokenizer": "whitespace",
        "filter": ["lowercase"]
    },
    "comma": {
        "type": "pattern",
        "pattern": r"\s*,\s*"
    },
    "sortable_exact": {
        "type": "custom",
        "tokenizer": "keyword",
        "filter": ["lowercase"]
    },
}

REMOVE_SETTING = None

ES_ENV_SETTINGS = {
    'icds': {
        'hqusers': {
            "number_of_replicas": 1,
        },
    },
}

ES_META = {
    # Default settings for all indexes on ElasticSearch
    'default': {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default', 'sortable_exact'),
        },
    },
    # Default settings for aliases on all environments (overrides default settings)
    'hqdomains': {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default', 'comma'),
        },
    },

    'hqapps': {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default'),
        },
    },

    'hqusers': {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 0,
            "analysis": _get_analysis('default'),
        },
    },
}


@six.python_2_unicode_compatible
class ElasticsearchIndexInfo(jsonobject.JsonObject):
    index = jsonobject.StringProperty(required=True)
    alias = jsonobject.StringProperty()
    type = jsonobject.StringProperty()
    mapping = jsonobject.DictProperty()

    def __str__(self):
        return '{} ({})'.format(self.alias, self.index)

    @property
    def meta(self):
        meta_settings = deepcopy(ES_META['default'])
        meta_settings.update(
            ES_META.get(self.alias, {})
        )
        meta_settings.update(
            ES_META.get(settings.SERVER_ENVIRONMENT, {}).get(self.alias, {})
        )

        overrides = copy(ES_ENV_SETTINGS)
        if settings.ES_SETTINGS is not None:
            overrides.update({settings.SERVER_ENVIRONMENT: settings.ES_SETTINGS})

        for alias in ['default', self.alias]:
            for key, value in overrides.get(settings.SERVER_ENVIRONMENT, {}).get(alias, {}).items():
                if value is REMOVE_SETTING:
                    del meta_settings['settings'][key]
                else:
                    meta_settings['settings'][key] = value

        return meta_settings

    def to_json(self):
        json = super(ElasticsearchIndexInfo, self).to_json()
        json['meta'] = self.meta
        return json


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


def assume_alias(es, index, alias):
    """
    This operation assigns the alias to the index and removes the alias
    from any other indices it might be assigned to.
    """
    if es.indices.exists_alias(None, alias):
        # this part removes the conflicting aliases
        alias_indices = list(es.indices.get_alias(alias))
        for aliased_index in alias_indices:
            es.indices.delete_alias(aliased_index, alias)
    es.indices.put_alias(index, alias)


def doc_exists(pillow, doc_id_or_dict):
    index_info = get_index_info_from_pillow(pillow)
    from corehq.elastic import doc_exists_in_es
    return doc_exists_in_es(index_info, doc_id_or_dict)


def get_index_info_from_pillow(pillow):
    return ElasticsearchIndexInfo(
        index=pillow.es_index,
        alias=pillow.es_alias,
        type=pillow.es_type,
        meta=pillow.es_meta,
        mapping=pillow.default_mapping,
    )
