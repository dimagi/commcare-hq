import logging
from couchdbkit import ChangesStream, ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import FormIndicatorDefinition, \
    CaseIndicatorDefinition, CaseDataInFormIndicatorDefinition
from corehq.apps.indicators.utils import get_namespaces, get_indicator_domains
from couchforms.models import XFormInstance
from mvp_docs.models import IndicatorXForm, IndicatorCase
from pillowtop.listener import BasicPillow

pillow_logging = logging.getLogger("pillowtop")
pillow_eval_logging = logging.getLogger("pillowtop_eval")


class MVPIndicatorPillowBase(BasicPillow):
    couch_filter = 'fluff_filter/domain_type'

    @property
    def extra_args(self):
        return {
            'domains': ' '.join(get_indicator_domains()),
            'doc_type': self.document_class._doc_type,
        }

    def run_burst(self):
        """
        Use this for testing pillows. Will run through the changes stream once.
        """
        changes_stream = ChangesStream(
            db=self.couch_db,
            since=self.since,
            filter=self.couch_filter,
            include_docs=self.include_docs,
            **self.extra_args
        )
        for change in changes_stream:
            if change:
                self.processor(change)

    def change_transform(self, doc_dict):
        domain = doc_dict.get('domain')
        if not domain:
            return
        namespaces = get_namespaces(domain)
        self.process_indicators(namespaces, domain, doc_dict)

    def process_indicators(self, namespaces, domain, doc_dict):
        raise NotImplementedError("Your pillow must implement this method.")


class MVPFormIndicatorPillow(MVPIndicatorPillowBase):
    document_class = XFormInstance
    use_locking = True

    def process_indicators(self, namespaces, domain, doc_dict):
        if not doc_dict.get('initial_processing_complete', False):
            return
        xmlns = doc_dict.get('xmlns')
        if not xmlns:
            return

        form_indicator_defs = []
        for namespace in namespaces:
            form_indicator_defs.extend(
                FormIndicatorDefinition.get_all(namespace, domain, xmlns=xmlns)
            )

        if not form_indicator_defs:
            return

        try:
            indicator_form = IndicatorXForm.wrap_for_indicator_db(doc_dict)
            indicator_form.update_indicators_in_bulk(
                form_indicator_defs, logger=pillow_eval_logging,
                save_on_update=False
            )
            indicator_form.save()
        except Exception as e:
            pillow_eval_logging.error(
                "Error creating for MVP Indicator for form %(form_id)s: "
                "%(error)s" % {
                    'form_id': doc_dict['_id'],
                    'error': e,
                },
            )
            raise


class MVPCaseIndicatorPillow(MVPIndicatorPillowBase):
    document_class = CommCareCase
    use_locking = True

    def process_indicators(self, namespaces, domain, doc_dict):
        case_type = doc_dict.get('type')
        if not case_type:
            return

        case_indicator_defs = []
        for namespace in namespaces:
            case_indicator_defs.extend(CaseIndicatorDefinition.get_all(
                namespace,
                domain,
                case_type=case_type
            ))

        try:
            indicator_case = IndicatorCase.wrap_for_indicator_db(doc_dict)
            indicator_case.update_indicators_in_bulk(
                case_indicator_defs, logger=pillow_eval_logging,
                save_on_update=False
            )
            indicator_case.save()
        except Exception as e:
            pillow_eval_logging.error(
                "Error creating for MVP Indicator for form %(form_id)s: "
                "%(error)s" % {
                    'form_id': doc_dict['_id'],
                    'error': e,
                },
            )
            raise

        # Now Update Data From Case to All Related Xforms (ewwww)
        xform_ids = doc_dict.get('xform_ids', [])
        if not xform_ids:
            return

        for xform_id in xform_ids:
            try:
                xform_dict = XFormInstance.get_db().get(xform_id)
                xform_doc = IndicatorXForm.wrap_for_indicator_db(xform_dict)
            except ResourceNotFound:
                pillow_eval_logging.error(
                    "Could not find an XFormInstance with id %(xform_id)s "
                    "related to Case %(case_id)s" % {
                        'xform_id': xform_id,
                        'case_id': doc_dict['_id'],
                    }
                )
                continue

            if not xform_doc.xmlns:
                continue
            related_xform_defs = []
            for namespace in namespaces:
                related_xform_defs.extend(
                    CaseDataInFormIndicatorDefinition.get_all(
                        namespace,
                        domain,
                        xmlns=xform_doc.xmlns
                    )
                )
            xform_doc.update_indicators_in_bulk(
                related_xform_defs,
                logger=pillow_eval_logging,
                save_on_update=False
            )
            xform_doc.save()
