import logging
import json
from casexml.apps.case.models import CommCareCase
from pillowtop.listener import BasicPillow, USE_NEW_CHANGES, old_changes, new_changes
from settings import INDICATOR_NAMESPACES, INDICATOR_DOMAINS

class CaseIndicatorPillow(BasicPillow):
    couch_db = CommCareCase.get_db()
    couch_filter = "indicators/indicatorless_casedocs"

    def __init__(self):
        self.couch_req_kwargs = dict(
            namespaces=",".join(INDICATOR_NAMESPACES),
            domains=",".join(INDICATOR_DOMAINS)
        )
        print "REQ KWARGS", self.couch_req_kwargs

    def change_transform(self, doc_dict):
        logging.info("change_transform CaseIndicatorPillow")
        logging.info("DOC ID %s computed %s" % (doc_dict.get('_id'), doc_dict.get('computed_')))
        return doc_dict

    def change_transport(self, doc_dict):
        return doc_dict

class FormIndicatorPillows(CaseIndicatorPillow):
    couch_filter = "indicators/indicatorless_xforms"
