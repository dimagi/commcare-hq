import copy
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from corehq.pillows.mappings.case_mapping import CASE_MAPPING, CASE_INDEX
from dimagi.utils.decorators.memoized import memoized
from .base import HQPillow
from django.conf import settings


UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"

class CasePillow(HQPillow):
    """
    Simple/Common Case properties Indexer
    """
    document_class = CommCareCase
    couch_filter = "case/casedocs"
    es_index_prefix = "hqcases"
    es_alias = "hqcases"
    es_type = "case"

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

        return {
            self.get_type_string(doc_dict): self.default_mapping
        }

    def get_type_string(self, doc_dict):
        return self.es_type
