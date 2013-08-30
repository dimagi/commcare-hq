import copy
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from corehq.pillows.mappings.case_mapping import CASE_MAPPING, CASE_INDEX
from dimagi.utils.decorators.memoized import memoized
from .base import HQPillow
from django.conf import settings
import logging


UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"

pillow_logging = logging.getLogger("pillowtop")
pillow_logging.setLevel(logging.INFO)

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

    def change_trigger(self, changes_dict):
        doc_dict = super(CasePillow, self).change_trigger(changes_dict)
        if doc_dict['doc_type'] == 'CommCareCase-Deleted':
            if self.doc_exists(doc_dict):
                self.get_es().delete(path=self.get_doc_path_typed(doc_dict))
            return None
        else:
            return doc_dict

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

    def change_transform(self, doc_dict):
        doc_ret = copy.deepcopy(doc_dict)
        if not doc_ret.get("owner_id"):
            if doc_ret.get("user_id"):
                doc_ret["owner_id"] = doc_ret["user_id"]
        return doc_ret
