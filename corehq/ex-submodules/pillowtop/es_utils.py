from copy import deepcopy

from dimagi.ext import jsonobject
from pillowtop.logger import pillow_logging

from corehq.apps.es.index.settings import (
    IndexSettingsKey,
    render_index_tuning_settings,
)
from corehq.apps.es.migration_operations import CreateIndex
from corehq.apps.es.transient_util import doc_adapter_from_info
from corehq.apps.es.client import manager
from corehq.util.es.elasticsearch import TransportError

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


def initialize_index_and_mapping(es, index_info):
    # TODO: Remove es param as it is unused
    index_exists = manager.index_exists(index_info.index)
    if not index_exists:
        initialize_index(index_info)
    assume_alias(index_info.index, index_info.alias)


def initialize_index(index_info):
    pillow_logging.info("Initializing elasticsearch index for [%s]" % index_info.type)
    CreateIndex(
        index_info.index,
        index_info.type,
        index_info.mapping,
        index_info.meta["settings"]["analysis"],
        index_info.hq_index_name,
    ).run()


def mapping_exists(index_info):
    try:
        return manager.index_get_mapping(index_info.index, index_info.type)
    except TransportError:
        return {}


def assume_alias(index, alias):
    """
    This operation assigns the alias to the index and removes the alias
    from any other indices it might be assigned to.
    """
    manager.index_put_alias(index, alias)
