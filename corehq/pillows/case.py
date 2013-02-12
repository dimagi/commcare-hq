import hashlib
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.pillows.mappings.case_mapping import CASE_MAPPING, CASE_INDEX
from pillowtop.listener import AliasedElasticPillow
from django.conf import settings


UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"

class CasePillow(AliasedElasticPillow):
    document_class = CommCareCase
    couch_filter = "case/casedocs"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index_prefix = "hqcases"
    es_alias = "hqcases"
    es_type = "case"
    es_meta = {}
    es_index = CASE_INDEX
    default_mapping = CASE_MAPPING

    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        if not hasattr(self, '_calc_meta'):
            self._calc_meta = self.calc_mapping_hash(self.default_mapping)
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
        #subsequent data added to it will be added automatically, but the date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all will be strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): CASE_MAPPING
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
