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

    @memoized
    def calc_meta(self):
        #todo: actually do this correctly

        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return self.calc_mapping_hash({"es_meta": self.es_meta,
                                       "mapping": self.default_mapping})
