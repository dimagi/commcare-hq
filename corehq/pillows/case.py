import copy
from casexml.apps.case.models import CommCareCase
from corehq.pillows.mappings.case_mapping import CASE_MAPPING, CASE_INDEX
from dimagi.utils.couch import LockManager
from dimagi.utils.decorators.memoized import memoized
from .base import HQPillow
import logging
from pillowtop.listener import lock_manager


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
    es_alias = "hqcases"
    es_type = "case"

    es_index = CASE_INDEX
    default_mapping = CASE_MAPPING

    def change_trigger(self, changes_dict):
        doc_dict, lock = lock_manager(
            super(CasePillow, self).change_trigger(changes_dict)
        )
        if doc_dict and doc_dict['doc_type'] == 'CommCareCase-Deleted':
            if self.doc_exists(doc_dict):
                self.get_es_new().delete(self.es_index, self.es_type, doc_dict['_id'])
            return None
        else:
            return LockManager(doc_dict, lock)

    @classmethod
    @memoized
    def calc_meta(cls):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return cls.calc_mapping_hash({
            'es_meta': cls.es_meta,
            'mapping': cls.default_mapping,
        })

    def change_transform(self, doc_dict):
        doc_ret = copy.deepcopy(doc_dict)
        if not doc_ret.get("owner_id"):
            if doc_ret.get("user_id"):
                doc_ret["owner_id"] = doc_ret["user_id"]
        return doc_ret
