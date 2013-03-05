from django.conf import settings

from casexml.apps.case.models import CommCareCase
from corehq.pillows.mappings.fullcase_mapping import FULL_CASE_MAPPING, FULL_CASE_INDEX
from pillowtop.listener import AliasedElasticPillow


UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"

class FullCasePillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """
    document_class = CommCareCase
    couch_filter = "case/casedocs"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_timeout = 600
    es_index_prefix = "full_cases"
    es_alias = "full_cases"
    es_type = "fullcase"
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
    es_index = FULL_CASE_INDEX
    default_mapping = FULL_CASE_MAPPING

    def change_trigger(self, changes_dict):
        """
        Override and check to ensure that the opened doc's domain matches
        those enabled for fully indexed case docs
        """
        doc_dict = super(FullCasePillow, self).change_trigger(changes_dict)
        domain = doc_dict.get('domain', None)
        if domain is None:
            domain = UNKNOWN_DOMAIN

        dynamic_domains = getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', [])
        if domain in dynamic_domains:
            return doc_dict
        else:
            return None

    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        if not hasattr(self, '_calc_meta'):
            self._calc_meta = self.calc_mapping_hash({"es_meta": self.es_meta,
                                                      "mapping": self.default_mapping})
        return self._calc_meta

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
        domain = doc_dict.get('domain', None)
        if domain is None:
            domain = UNKNOWN_DOMAIN

        return {
            self.get_type_string(doc_dict): self.default_mapping
        }

    def get_type_string(self, doc_dict):
        domain = doc_dict.get('domain', None)
        if domain is None:
            domain = UNKNOWN_DOMAIN
        case_type = doc_dict.get('type', None)
        if case_type is None:
            case_type = UNKNOWN_TYPE

        ret = "%(type)s_%(domain)s__%(case_type)s" % {
            'type': self.es_type,
            'domain': domain.lower(),
            'case_type': case_type.lower(),
        }
        return ret
