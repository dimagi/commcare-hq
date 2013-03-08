from casexml.apps.case.models import CommCareCase
from corehq.pillows.mappings.case_mapping import CASE_MAPPING, CASE_INDEX
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import AliasedElasticPillow
from django.conf import settings


UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"

class CasePillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """
    document_class = CommCareCase
    couch_filter = "case/casedocs"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_timeout = 600
    es_index_prefix = "hqcases"
    es_alias = "hqcases"
    es_type = "case"
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
    es_index = CASE_INDEX
    default_mapping = CASE_MAPPING

    @memoized
    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return self.calc_mapping_hash({"es_meta": self.es_meta,
                                                      "mapping": self.default_mapping})

    def get_mapping_from_type(self, doc_dict):
        """
        Define mapping uniquely to the domain_type document.
        See below on why date_detection is False

        NOTE: DO NOT MODIFY THIS UNLESS ABSOLUTELY NECESSARY. A CHANGE BELOW WILL GENERATE A NEW
        HASH FOR THE INDEX NAME REQUIRING A REINDEX+RE-ALIAS. THIS IS A SERIOUSLY RESOURCE
        INTENSIVE OPERATION THAT REQUIRES SOME CAREFUL LOGISTICS TO MIGRATE
        """
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all are strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): self.default_mapping
        }

    def get_type_string(self, doc_dict):
        return self.es_type
