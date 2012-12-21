import logging
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormIndicatorDefinition, CaseDataInFormIndicatorDefinition
from couchforms.models import XFormInstance
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import BasicPillow
from settings import INDICATOR_CONFIG

class IndicatorPillowBase(BasicPillow):
    indicator_document_type = None
    only_use_fresh_docs = True

    @property
    @memoized
    def indicator_domains(self):
        return INDICATOR_CONFIG.keys()

    def change_transform(self, doc_dict):
        if self.doc_is_valid(doc_dict):
            indicators = self.get_indicators_by_doc(doc_dict)
            if indicators:
                doc = self.get_document(doc_dict)
                self.update_indicators_in_doc_instance(doc, indicators)
                return doc._doc
        return doc_dict

    def is_document_update(self, marker, doc_dict):
        return True

    def change_transport(self, doc_dict):
        return doc_dict

    def get_indicators_by_doc(self, doc_dict):
        raise NotImplementedError

    def get_document(self, doc_dict):
        raise NotImplementedError

    def doc_is_valid(self, doc_dict):
        if self.indicator_document_type is None:
            raise NotImplementedError("you must specify an indicator document type")

        computed_dict = doc_dict.get('computed_')
        domain = doc_dict.get('domain')
        if (computed_dict is not None
            and domain in self.indicator_domains
            and doc_dict.get('doc_type') == self.indicator_document_type.__name__
            and doc_dict.get('initial_processing_complete')):
            namespaces = INDICATOR_CONFIG[domain]
            for namespace in namespaces:
                if not self.only_use_fresh_docs:
                    marker = doc_dict.get('computed_', {}).get(self.get_marker_slug(namespace))
                    return self.is_document_update(marker, doc_dict)
                elif namespace not in computed_dict:
                    return True
        return False

    @classmethod
    def update_indicators_in_doc_instance(cls, doc_instance, indicators):
        for indicator in indicators:
            if not cls.only_use_fresh_docs:
                doc_instance.computed_[cls.get_marker_slug(indicator.namespace)] = cls.get_change_marker(doc_instance)
            updated_status = doc_instance.update_indicator(indicator)
            if updated_status:
                logging.info("Set %(doc_type)s indicator %(indicator_slug)s in namespace %(namespace)s: %(doc_id)s" % {
                    'doc_type': doc_instance.doc_type,
                    'indicator_slug': indicator.slug,
                    'namespace': indicator.namespace,
                    'doc_id': doc_instance._id,
                    })

    @classmethod
    def get_change_marker(cls, doc_dict):
        return []

    @classmethod
    def get_marker_slug(cls, namespace):
        return "%s__marker__" % namespace


class CaseIndicatorPillow(IndicatorPillowBase):
    couch_db = CommCareCase.get_db()
    indicator_document_type = CommCareCase
    only_use_fresh_docs = False
    # todo: should maybe use this filter here? it takes so long to update, though...
    # couch_filter = "indicators/indicatorless_casedocs"

    def get_indicators_by_doc(self, doc_dict):
        indicators = []

        case_type = doc_dict.get('type')
        domain = doc_dict.get('domain')
        form_ids = doc_dict.get('xform_ids') or []

        if case_type and domain:
            # relevant namespaces
            namespaces = INDICATOR_CONFIG[domain]

            for namespace in namespaces:
                # need all the relevant Case Indicator Defs
                indicators.extend(CaseIndicatorDefinition.get_all(namespace, domain, case_type=case_type))

                # we also need to update forms that are related to this case and might use data which
                # may have just been updated
                for form_id in form_ids:
                    try:
                        xform = XFormInstance.get(form_id)
                        if xform.xmlns and isinstance(xform, XFormInstance):
                            case_related_indicators = CaseDataInFormIndicatorDefinition.get_all(namespace, domain,
                                xmlns=xform.xmlns)
                            logging.info("Grabbed Related XForm %s and now processing %d indicators." %
                                         (form_id, len(case_related_indicators)))
                            FormIndicatorPillow.update_indicators_in_doc_instance(xform, case_related_indicators)
                            logging.info("Done processing indicators.")
                    except Exception as e:
                        logging.error("Error grabbing related xform for CommCareCase %s: %s" % (doc_dict['_id'], e))

        return indicators

    def get_document(self, doc_dict):
        return CommCareCase.get(doc_dict['_id'])

    @classmethod
    def get_change_marker(cls, doc_instance):
        if isinstance(doc_instance, CommCareCase):
            return len(doc_instance.xform_ids) if doc_instance.xform_ids else 0
        return super(CaseIndicatorPillow, cls).get_change_marker(doc_instance)

    def is_document_update(self, marker, doc_dict):
        xform_ids = doc_dict.get('xform_ids') or []
        return len(xform_ids) > marker


class FormIndicatorPillow(IndicatorPillowBase):
    couch_db = XFormInstance.get_db()
    indicator_document_type = XFormInstance
    # todo: should maybe use this filter here? it takes so long to update, though...
    # couch_filter = "indicators/indicatorless_xforms"

    def get_indicators_by_doc(self, doc_dict):
        indicators = []
        xmlns = doc_dict.get('xmlns')
        domain = doc_dict.get('domain')
        if xmlns and domain:
            namespaces = INDICATOR_CONFIG[domain]
            for namespace in namespaces:
                indicators.extend(FormIndicatorDefinition.get_all(namespace, domain, xmlns=xmlns))
        return indicators

    def get_document(self, doc_dict):
        return XFormInstance.get(doc_dict['_id'])
