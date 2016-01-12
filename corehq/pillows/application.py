from corehq.apps.app_manager.models import ApplicationBase
from corehq.pillows.mappings.app_mapping import APP_INDEX, APP_MAPPING
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import AliasedElasticPillow
from django.conf import settings


class AppPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = ApplicationBase
    couch_filter = "app_manager/all_apps"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_timeout = 60
    es_alias = "hqapps"
    es_type = "app"
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                }
            }
        }
    }
    es_index = APP_INDEX
    default_mapping = APP_MAPPING

    @classmethod
    def get_unique_id(cls):
        return APP_INDEX
