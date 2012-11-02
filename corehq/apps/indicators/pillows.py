import logging
import json
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import IndicatorDefinition
from pillowtop.listener import BasicPillow, USE_NEW_CHANGES, old_changes, new_changes
from settings import INDICATOR_CONFIG

class CaseIndicatorPillow(BasicPillow):
    couch_db = CommCareCase.get_db()
    couch_filter = "indicators/indicatorless_casedocs"

    def __init__(self):
        namespaces = set()
        for nlist in INDICATOR_CONFIG.values():
            for namespace in nlist:
                namespaces.add(namespace)
        self.couch_req_kwargs = dict(
            namespaces=",".join(namespaces),
            domains=",".join(INDICATOR_CONFIG.keys())
        )
        print "REQ KWARGS", self.couch_req_kwargs

    def change_transform(self, doc_dict):
        logging.info("change_transform CaseIndicatorPillow")
        logging.info("DOC ID %s computed %s" % (doc_dict.get('_id'), doc_dict.get('computed_')))
#        self.get_indicators_by_doc(doc_dict)
        return doc_dict

    def change_transport(self, doc_dict):
        return doc_dict

    def get_indicators_by_doc(self, doc_dict):
        case_type = doc_dict.get('type')
        domain = doc_dict.get('domain')
        namespaces = INDICATOR_CONFIG.get(domain, [])
        for namespace in namespaces:
            indicators = IndicatorDefinition.get_all(namespace, domain, case_type=case_type)
            logging.info("All indicators in namespace %s: %s" % (namespace, ", ".join([i.slug for i in indicators])))


class FormIndicatorPillows(CaseIndicatorPillow):
    couch_filter = "indicators/indicatorless_xforms"
