from pillowtop.logger import pillow_logging

from corehq.apps.es.client import manager
from corehq.apps.es.index.settings import IndexSettingsKey
from corehq.apps.es.migration_operations import CreateIndex
from corehq.util.es.elasticsearch import TransportError

XFORM_HQ_INDEX_NAME = IndexSettingsKey.FORMS
CASE_HQ_INDEX_NAME = IndexSettingsKey.CASES
USER_HQ_INDEX_NAME = IndexSettingsKey.USERS
DOMAIN_HQ_INDEX_NAME = IndexSettingsKey.DOMAINS
APP_HQ_INDEX_NAME = IndexSettingsKey.APPS
GROUP_HQ_INDEX_NAME = IndexSettingsKey.GROUPS
SMS_HQ_INDEX_NAME = IndexSettingsKey.SMS
CASE_SEARCH_HQ_INDEX_NAME = IndexSettingsKey.CASE_SEARCH


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


def initialize_index_and_mapping(adapter):
    index_exists = manager.index_exists(adapter.index_name)
    if not index_exists:
        initialize_index(adapter)


def initialize_index(adapter):
    pillow_logging.info("Initializing elasticsearch index for [%s]" % adapter.type)
    CreateIndex(
        adapter.index_name,
        adapter.type,
        adapter.mapping,
        adapter.analysis,
        adapter.settings_key,
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
