import logging
import json
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import IndicatorDefinition, CaseIndicatorDefinition, FormIndicatorDefinition
from couchforms.models import XFormInstance
from pillowtop.listener import BasicPillow, USE_NEW_CHANGES, old_changes, new_changes
from settings import INDICATOR_CONFIG

class IndicatorPillowBase(BasicPillow):

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
        indicators = self.get_indicators_by_doc(doc_dict)
        if indicators:
            doc = self.get_document(doc_dict)
            for indicator in indicators:
                logging.info("set indicator %s" % indicator.slug)
                doc.set_definition(indicator)
            doc.save()
            return doc._doc
        return doc_dict

    def change_transport(self, doc_dict):
        return doc_dict

    def get_indicators_by_doc(self, doc_dict):
        raise NotImplementedError

    def get_document(self, doc_dict):
        raise NotImplementedError

class CaseIndicatorPillow(BasicPillow):
    couch_db = CommCareCase.get_db()
    couch_filter = "indicators/indicatorless_casedocs"

    def get_indicators_by_doc(self, doc_dict):
        indicators = []
        case_type = doc_dict.get('type')
        domain = doc_dict.get('domain')
        if case_type and domain:
            namespaces = INDICATOR_CONFIG.get(domain, [])
            print "NAMESPACES", namespaces
            for namespace in namespaces:
                indicators.extend(CaseIndicatorDefinition.get_all(namespace, domain, case_type=case_type))
                logging.info("All indicators in namespace %s: %s" % (namespace, ", ".join([i.slug for i in indicators])))
        return indicators

    def get_document(self, doc_dict):
        return CommCareCase.get(doc_dict['_id'])


class FormIndicatorPillows(CaseIndicatorPillow):
    couch_db = XFormInstance.get_db()
    couch_filter = "indicators/indicatorless_xforms"

    def get_indicators_by_doc(self, doc_dict):
        indicators = []
        xmlns = doc_dict.get('xmlns')
        domain = doc_dict.get('domain')
        if xmlns and domain:
            namespaces = INDICATOR_CONFIG.get(domain, [])
            for namespace in namespaces:
                indicators.extend(FormIndicatorDefinition.get_all(namespace, domain, xmlns=xmlns))
                logging.info("All indicators in namespace %s: %s" % (namespace, ", ".join([i.slug for i in indicators])))
        return indicators

    def get_document(self, doc_dict):
        return XFormInstance.get(doc_dict['_id'])