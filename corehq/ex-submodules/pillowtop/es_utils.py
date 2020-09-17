from corehq.util.es.interface import ElasticsearchInterface
from dimagi.ext import jsonobject
from django.conf import settings
from copy import copy, deepcopy
from datetime import datetime
from corehq.pillows.mappings.utils import transform_for_es7
from corehq.util.es.elasticsearch import TransportError, NotFoundError
from pillowtop.logger import pillow_logging


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
    }
}

REMOVE_SETTING = None

ES_ENV_SETTINGS = {
    'icds': {
        'hqusers': {
            "number_of_replicas": 1,
        },
    },
}

XFORM_HQ_INDEX_NAME = "xforms"
CASE_HQ_INDEX_NAME = "hqcases"
USER_HQ_INDEX_NAME = "hqusers"
DOMAIN_HQ_INDEX_NAME = "hqdomains"
APP_HQ_INDEX_NAME = "hqapps"
GROUP_HQ_INDEX_NAME = "hqgroups"
SMS_HQ_INDEX_NAME = "smslogs"
REPORT_CASE_HQ_INDEX_NAME = "report_cases"
REPORT_XFORM_HQ_INDEX_NAME = "report_xforms"
CASE_SEARCH_HQ_INDEX_NAME = "case_search"
TEST_HQ_INDEX_NAME = "pillowtop_tests"

ES_INDEX_SETTINGS = {
    # Default settings for all indexes on ElasticSearch
    'default': {
        "settings": {
            "number_of_replicas": 0,
            "number_of_shards": 5,
            "analysis": _get_analysis('default'),
        },
    },
    # Default settings for aliases on all environments (overrides default settings)
    DOMAIN_HQ_INDEX_NAME: {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default', 'comma'),
        },
    },

    APP_HQ_INDEX_NAME: {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default'),
        },
    },

    USER_HQ_INDEX_NAME: {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 0,
            "analysis": _get_analysis('default'),
        },
    },
}


class ElasticsearchIndexInfo(jsonobject.JsonObject):
    index = jsonobject.StringProperty(required=True)
    alias = jsonobject.StringProperty()
    type = jsonobject.StringProperty()
    ilm_config = jsonobject.StringProperty(default="")
    mapping = jsonobject.DictProperty()
    hq_index_name = jsonobject.StringProperty()

    def __str__(self):
        return '{} ({})'.format(self.alias, self.index)

    @property
    def template_name(self):
        return f"{self.index}_template"

    @property
    def meta(self):
        meta_settings = deepcopy(ES_INDEX_SETTINGS['default'])
        meta_settings.update(
            ES_INDEX_SETTINGS.get(self.hq_index_name, {})
        )
        meta_settings.update(
            ES_INDEX_SETTINGS.get(settings.SERVER_ENVIRONMENT, {}).get(self.hq_index_name, {})
        )

        overrides = copy(ES_ENV_SETTINGS)
        if settings.ES_SETTINGS is not None:
            overrides.update({settings.SERVER_ENVIRONMENT: settings.ES_SETTINGS})

        for hq_index_name in ['default', self.hq_index_name]:
            for key, value in overrides.get(settings.SERVER_ENVIRONMENT, {}).get(hq_index_name, {}).items():
                if value is REMOVE_SETTING:
                    del meta_settings['settings'][key]
                else:
                    meta_settings['settings'][key] = value

        return meta_settings

    def to_json(self):
        json = super(ElasticsearchIndexInfo, self).to_json()
        json['meta'] = self.meta
        return json


def set_index_reindex_settings(es, index):
    """
    Set a more optimized setting setup for fast reindexing
    """
    from pillowtop.index_settings import INDEX_REINDEX_SETTINGS
    return ElasticsearchInterface(es).update_index_settings(index, INDEX_REINDEX_SETTINGS)


def set_index_normal_settings(es, index):
    """
    Normal indexing configuration
    """
    from pillowtop.index_settings import INDEX_STANDARD_SETTINGS
    return ElasticsearchInterface(es).update_index_settings(index, INDEX_STANDARD_SETTINGS)


max_docs_policy = {
    "policy": {
        "phases": {
            "hot": {
                "actions": {
                    "rollover": {
                        "max_docs": "2",
                    }
                }
            }
        }
    }
}

MAX_DOCS = 'max_docs'

ILM_CONFIGS = {
    MAX_DOCS: max_docs_policy
}


def initialize_index_and_mapping(es, index_info):
    if index_info.ilm_config and settings.ELASTICSEARCH_MAJOR_VERSION == 7:
        setup_ilm_index(es, index_info)
    else:
        index_exists = es.indices.exists(index_info.index)
        if not index_exists:
            initialize_index(es, index_info)
        assume_alias(es, index_info.index, index_info.alias)


def initialize_index(es, index_info):
    index = index_info.index
    mapping = transform_for_es7(index_info.mapping)
    mapping['_meta']['created'] = datetime.isoformat(datetime.utcnow())
    meta = copy(index_info.meta)
    meta.update({'mappings': mapping})
    pillow_logging.info("Initializing elasticsearch index for [%s]" % index_info.type)
    es.indices.create(index=index, body=meta)
    set_index_normal_settings(es, index)


def get_ilm_tempalte(index_info):
    assert index_info.ilm_config
    mapping = transform_for_es7(index_info.mapping)
    mapping['_meta']['created'] = datetime.isoformat(datetime.utcnow())
    meta = copy(index_info.meta)
    meta.update({'mappings': mapping})
    meta['settings'].update({
        "index.lifecycle.name": index_info.ilm_config,
        "index.lifecycle.rollover_alias": index_info.alias
    })
    return {
        "index_patterns": [IndexPattern(index_info.index).index_patterns],
        "template": meta
    }


class IndexPattern(object):

    def __init__(self, name):
        self.name = name

    @property
    def index_patterns(self):
        return f"{self.name}-*"

    @property
    def initial_index(self):
        return f"{self.name}-000001"


def setup_ilm_index(es, index_info):
    # setup policy
    ilm_config = index_info.ilm_config
    try:
        es.ilm.get_lifecycle(ilm_config)
    except NotFoundError:
        es.ilm.put_lifecycle(ilm_config, ILM_CONFIGS[ilm_config])
    # setup template
    try:
        es.indices.get_index_template(index_info.template_name)
    except NotFoundError:
        es.indices.put_index_template(
            index_info.template_name,
            get_ilm_tempalte(index_info)
        )
    # bootstrap initial index
    indices = es.indices.resolve_index(index_info.alias)
    if not indices.get('indices'):
        es.indices.create(
            IndexPattern(index_info.index).initial_index,
            {
                "aliases": {
                    index_info.alias: {"is_write_index": True}
                }
            }
        )


def mapping_exists(es, index_info):
    try:
        if settings.ELASTICSEARCH_MAJOR_VERSION == 7:
            return es.indices.get_mapping(index_info.index).get(index_info.index, {}).get('mappings', None)
        else:
            return es.indices.get_mapping(index_info.index, index_info.type)
    except TransportError:
        return {}


def assume_alias(es, index, alias):
    """
    This operation assigns the alias to the index and removes the alias
    from any other indices it might be assigned to.
    """
    if es.indices.exists_alias(name=alias):
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
