import logging
from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.utils import get_indicator_domains, get_namespaces
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormIndicatorDefinition, CaseDataInFormIndicatorDefinition
from couchforms.models import XFormInstance
from pillowtop.listener import BasicPillow

pillow_logging = logging.getLogger("pillowtop")


class IndicatorPillowBase(BasicPillow):
    only_use_fresh_docs = True
    couch_filter = 'fluff_filter/domain_type'

    @property
    def extra_args(self):
        return {
            'domains': ' '.join(get_indicator_domains()),
            'doc_type': self.document_class._doc_type,
        }

    def change_transform(self, doc_dict):
        domain = doc_dict.get('domain')
        if not domain:
            return

        namespaces = get_namespaces(domain)
        if namespaces and 'computed_' in doc_dict:
            self.process_indicators(doc_dict, domain, namespaces)

    def process_indicators(self, doc_dict, domain, namespaces):
        raise NotImplementedError("You need to implement process_indicators")


class CaseIndicatorPillow(IndicatorPillowBase):
    document_class = CommCareCase

    def process_indicators(self, doc_dict, domain, namespaces):
        case_type = doc_dict.get('type')
        if not case_type:
            return

        case_indicators = []
        for namespace in namespaces:
            case_indicators.extend(CaseIndicatorDefinition.get_all(namespace, domain, case_type=case_type))

        if case_indicators:
            case_doc = CommCareCase.get(doc_dict['_id'])
            case_doc.update_indicators_in_bulk(case_indicators, logger=pillow_logging)

        xform_ids = doc_dict.get('xform_ids', [])
        for namespace in namespaces:
            for xform_id in xform_ids:
                try:
                    xform_doc = XFormInstance.get(xform_id)
                    if not xform_doc.xmlns:
                        continue
                    related_xform_indicators = CaseDataInFormIndicatorDefinition.get_all(namespace, domain,
                                                                                         xmlns=xform_doc.xmlns)
                    xform_doc.update_indicators_in_bulk(related_xform_indicators, logger=pillow_logging)
                except ResourceNotFound:
                    pillow_logging.error("[INDICATOR %(namespace)s %(domain)s] Tried to form indicator %(xform_id)s "
                                         "from case %(case_id)s and failed." % {
                                             'namespace': namespace,
                                             'domain': domain,
                                             'xform_id': xform_id,
                                             'case_id': doc_dict['_id'],
                                         })


class FormIndicatorPillow(IndicatorPillowBase):
    document_class = XFormInstance

    def process_indicators(self, doc_dict, domain, namespaces):
        if not doc_dict.get('inital_processing_complete', False):
            # Make sure we don't update the indicators before the XFormPillows and CasePillows.
            return

        xmlns = doc_dict.get('xmlns')
        if not xmlns:
            pillow_logging.warning('[INDICATOR %(domain)s] Could not find XMLS while '
                                   'processing indicator for %(xform_id)s' % {
                                       'domain': domain,
                                       'xform_id': doc_dict['_id'],
                                   })
            return

        indicators = []
        for namespace in namespaces:
            indicators.extend(FormIndicatorDefinition.get_all(namespace, domain, xmlns=xmlns))

        if indicators:
            xform_doc = XFormInstance.get(doc_dict['_id'])
            xform_doc.update_indicators_in_bulk(indicators, logger=pillow_logging)
