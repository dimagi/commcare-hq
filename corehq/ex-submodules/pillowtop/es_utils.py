from copy import deepcopy
from datetime import datetime

from corehq.apps.es.index.settings import (
    IndexSettingsKey,
    render_index_tuning_settings,
)
from corehq.apps.es.transient_util import doc_adapter_from_info
from corehq.util.es.elasticsearch import TransportError
from corehq.util.es.interface import ElasticsearchInterface
from dimagi.ext import jsonobject
from pillowtop.logger import pillow_logging

XFORM_HQ_INDEX_NAME = IndexSettingsKey.FORMS
CASE_HQ_INDEX_NAME = IndexSettingsKey.CASES
USER_HQ_INDEX_NAME = IndexSettingsKey.USERS
DOMAIN_HQ_INDEX_NAME = IndexSettingsKey.DOMAINS
APP_HQ_INDEX_NAME = IndexSettingsKey.APPS
GROUP_HQ_INDEX_NAME = IndexSettingsKey.GROUPS
SMS_HQ_INDEX_NAME = IndexSettingsKey.SMS
CASE_SEARCH_HQ_INDEX_NAME = IndexSettingsKey.CASE_SEARCH


class ElasticsearchIndexInfo(jsonobject.JsonObject):
    index = jsonobject.StringProperty(required=True)
    alias = jsonobject.StringProperty()
    type = jsonobject.StringProperty()
    mapping = jsonobject.DictProperty()
    hq_index_name = jsonobject.StringProperty()

    def __str__(self):
        return '{} ({})'.format(self.alias, self.index)

    @property
    def meta(self):
        adapter = doc_adapter_from_info(self)
        settings = {"analysis": deepcopy(adapter.analysis)}
        settings.update(render_index_tuning_settings(adapter.settings_key))
        return {"settings": settings}

    def to_json(self):
        json = super(ElasticsearchIndexInfo, self).to_json()
        json['meta'] = self.meta
        return json


def set_index_reindex_settings(es, index):
    """
    Set a more optimized setting setup for fast reindexing
    """
    return ElasticsearchInterface(es).update_index_settings_reindex(index)


def set_index_normal_settings(es, index):
    """
    Normal indexing configuration
    """
    return ElasticsearchInterface(es).update_index_settings_standard(index)


def initialize_index_and_mapping(es, index_info):
    index_exists = es.indices.exists(index_info.index)
    if not index_exists:
        initialize_index(es, index_info)
    assume_alias(es, index_info.index, index_info.alias)


def initialize_index(es, index_info):
    # WARNING: Do not make copies of JsonObject properties, those objects have
    #          some nasty bugs that will bite in really obscure ways.
    #          For example:
    # >>> from copy import copy
    # >>> from corehq.pillows.mappings import GROUP_INDEX_INFO as index_info
    # >>> list(index_info.meta)
    # ['settings']
    # >>> list(index_info.to_json()['meta'])
    # ['settings']
    # >>> meta = copy(index_info.meta)
    # >>> meta.update({'mappings': None})
    # >>> list(index_info.meta)
    # ['settings']
    # >>> list(index_info.to_json()['meta'])
    # ['settings', 'mappings']
    index = index_info.index
    mapping = dict(index_info.mapping)
    mapping["_meta"] = dict(mapping.pop("_meta", {}))
    mapping['_meta']['created'] = datetime.isoformat(datetime.utcnow())
    meta = dict(index_info.meta)
    meta.update({'mappings': {index_info.type: mapping}})

    pillow_logging.info("Initializing elasticsearch index for [%s]" % index_info.type)
    es.indices.create(index=index, body=meta)
    set_index_normal_settings(es, index)


def mapping_exists(es, index_info):
    try:
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


def get_index_info_from_pillow(pillow):
    return ElasticsearchIndexInfo(
        index=pillow.es_index,
        alias=pillow.es_alias,
        type=pillow.es_type,
        meta=pillow.es_meta,
        mapping=pillow.default_mapping,
    )
