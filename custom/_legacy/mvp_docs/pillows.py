import logging
from couchdbkit import ChangesStream, ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import FormIndicatorDefinition, \
    CaseIndicatorDefinition, CaseDataInFormIndicatorDefinition
from corehq.apps.indicators.utils import get_indicator_domains
from corehq.pillows.utils import get_deleted_doc_types
from couchforms.models import XFormInstance
from mvp_docs.models import IndicatorXForm, IndicatorCase
from pillowtop.listener import BasicPillow

pillow_logging = logging.getLogger("pillowtop")
pillow_eval_logging = logging.getLogger("pillowtop_eval")


class MVPIndicatorPillowBase(BasicPillow):
    indicator_class = None
    couch_filter = 'hqadmin/domains_and_doc_types'

    @property
    def extra_args(self):
        return {
            'domains': ' '.join(get_indicator_domains()),
            'doc_types': ' '.join([self._main_doc_type] + self._deleted_doc_types),
        }

    @property
    def _main_doc_type(self):
        return self.document_class._doc_type

    @property
    def _deleted_doc_types(self):
        return get_deleted_doc_types(self._main_doc_type)

    def change_transform(self, doc_dict):
        from corehq.apps.indicators.utils import get_namespaces
        doc_type = doc_dict.get('doc_type')
        if doc_type in self._deleted_doc_types:
            self._delete_doc(doc_dict)

        else:
            domain = doc_dict.get('domain')
            if not domain:
                return
            namespaces = get_namespaces(domain)
            self.process_indicators(namespaces, domain, doc_dict)

    def process_indicators(self, namespaces, domain, doc_dict):
        raise NotImplementedError("Your pillow must implement this method.")

    def _delete_doc(self, doc_dict):
        doc = self.indicator_class.wrap_for_indicator_db(doc_dict)
        if doc.exists_in_database():
            doc.delete()


class MVPFormIndicatorPillow(MVPIndicatorPillowBase):
    document_class = XFormInstance
    indicator_class = IndicatorXForm
    use_locking = True

    def process_indicators(self, namespaces, domain, doc_dict):
        if not doc_dict.get('initial_processing_complete', False):
            return
        xmlns = doc_dict.get('xmlns')
        if not xmlns:
            return

        form_indicator_defs = get_form_indicators(namespaces, domain, xmlns)
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
    indicator_class = IndicatorCase
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
            related_xform_indicators = []
            try:
                # first try to get the doc from the indicator DB
                xform_doc = IndicatorXForm.get(xform_id)
            except ResourceNotFound:
                # if that fails fall back to the main DB
                try:
                    xform_dict = XFormInstance.get_db().get(xform_id)
                    xform_doc = IndicatorXForm.wrap_for_indicator_db(xform_dict)
                    related_xform_indicators = get_form_indicators(namespaces, domain, xform_doc.xmlns)
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

            for namespace in namespaces:
                related_xform_indicators.extend(
                    CaseDataInFormIndicatorDefinition.get_all(
                        namespace,
                        domain,
                        xmlns=xform_doc.xmlns
                    )
                )
            xform_doc.update_indicators_in_bulk(
                related_xform_indicators,
                logger=pillow_eval_logging,
                save_on_update=False
            )
            xform_doc.save()


def get_form_indicators(namespaces, domain, xmlns):
    return [
        indicator for namespace in namespaces
        for indicator in FormIndicatorDefinition.get_all(namespace, domain, xmlns=xmlns)
    ]
