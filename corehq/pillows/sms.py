from corehq.apps.sms.models import SMSLog
from corehq.pillows.mappings.sms_mapping import SMS_MAPPING, SMS_INDEX
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import AliasedElasticPillow
from django.conf import settings


class SMSPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = SMSLog   # while this index includes all users,
                                    # I assume we don't care about querying on properties specfic to WebUsers
    couch_filter = "sms/all_logs"
    es_timeout = 60
    es_alias = "smslogs"
    es_type = "sms"
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
    es_index = SMS_INDEX
    default_mapping = SMS_MAPPING

    @classmethod
    @memoized
    def calc_meta(cls):
        #todo: actually do this correctly

        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return cls.calc_mapping_hash({"es_meta": cls.es_meta, "mapping": cls.default_mapping})
