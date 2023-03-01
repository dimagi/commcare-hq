from copy import deepcopy

from corehq.apps.es.index.settings import (
    IndexSettingsKey,
    render_index_tuning_settings,
)
from corehq.apps.es.migration_operations import CreateIndex
from corehq.apps.es.transient_util import doc_adapter_from_info
from corehq.apps.es.client import manager
from corehq.util.es.elasticsearch import TransportError
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


def set_index_reindex_settings(index):
    """
    Set a more optimized setting setup for fast reindexing
    """
    return manager.index_configure_for_reindex(index)


def set_index_normal_settings(index):
    """
    Normal indexing configuration
    """
    return manager.index_configure_for_standard_ops(index)


def initialize_index_and_mapping(es, index_info_or_adapter):
    # TODO: Remove es param as it is unused
    adapter = _get_adapter(index_info_or_adapter)
    if not manager.index_exists(adapter.index_name):
        initialize_index(adapter)


def initialize_index(index_info_or_adapter):
    adapter = _get_adapter(index_info_or_adapter)
    pillow_logging.info(f"Initializing elasticsearch index for [{adapter.type}]")
    CreateIndex(
        adapter.index_name,
        adapter.type,
        adapter.mapping,
        adapter.analysis,
        adapter.settings_key,
    ).run()


def mapping_exists(index_info_or_adapter):
    adapter = _get_adapter(index_info_or_adapter)
    try:
        return manager.index_get_mapping(adapter.index_name, adapter.type)
    except TransportError:
        return {}


def _get_adapter(index_info_or_adapter):
    if isinstance(index_info_or_adapter, ElasticsearchIndexInfo):
        return doc_adapter_from_info(index_info_or_adapter)
    return index_info_or_adapter
