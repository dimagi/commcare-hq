from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
from pillowtop.listener import AliasedElasticPillow


class AppPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = ApplicationBase
    couch_filter = "app_manager/all_apps"
    es_timeout = 60
    es_alias = APP_INDEX_INFO.alias
    es_type = APP_INDEX_INFO.type
    es_meta = APP_INDEX_INFO.meta
    es_index = APP_INDEX_INFO.index
    default_mapping = APP_INDEX_INFO.mapping

    def change_transform(self, doc_dict):
        # perform any lazy migrations
        doc = get_correct_app_class(doc_dict).wrap(doc_dict)
        return doc.to_json()
