from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from couchdbkit import ResourceNotFound

from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import FormIndicatorDefinition, \
    CaseIndicatorDefinition, CaseDataInFormIndicatorDefinition
from corehq.apps.indicators.utils import get_indicator_domains
from corehq.pillows.utils import get_deleted_doc_types
from couchforms.models import XFormInstance
from dimagi.utils.couch import LockManager
from memoized import memoized
from mvp_docs.models import IndicatorXForm, IndicatorCase
from pillowtop.checkpoints.manager import PillowCheckpoint, \
    PillowCheckpointEventHandler
from pillowtop.checkpoints.util import get_machine_id
from pillowtop.feed.couch import CouchChangeFeed
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.interface import PillowProcessor

pillow_logging = logging.getLogger("pillowtop")


def _lock_manager(obj):
    if isinstance(obj, LockManager):
        return obj
    else:
        return LockManager(obj, None)


class MVPIndicatorProcessorBase(PillowProcessor):
    document_class = None
    indicator_class = None

    def process_change(self, pillow_instance, change):
        from corehq.apps.indicators.utils import get_namespaces

        with _lock_manager(self._get_lock(change)):
            domain = _domain_for_change(change)
            doc_type = _doc_type_for_change(change)
            if self._should_process_change(domain, doc_type):
                doc_dict = change.get_document()
                if change.deleted or doc_type in self._deleted_doc_types:
                    self._delete_doc(change.get_document())
                    return

                namespaces = get_namespaces(domain)
                self.process_indicators(namespaces, domain, doc_dict)

    def process_indicators(self, namespaces, domain, doc_dict):
        raise NotImplementedError("Your pillow must implement this method.")

    def _get_lock(self, change):
        lock = self.document_class.get_obj_lock_by_id(change.id)
        lock.acquire()
        return LockManager(None, lock)

    def _delete_doc(self, doc_dict):
        doc = self.indicator_class.wrap_for_indicator_db(doc_dict)
        if doc.exists_in_database():
            doc.delete()

    def _should_process_change(self, domain, doc_type):
        return domain and domain in self.domains and doc_type in self.doc_types

    @property
    @memoized
    def domains(self):
        return get_indicator_domains()

    @property
    def _main_doc_type(self):
        return self.document_class._doc_type

    @property
    def _deleted_doc_types(self):
        return get_deleted_doc_types(self._main_doc_type)

    @property
    def doc_types(self):
        return [self._main_doc_type] + self._deleted_doc_types


def _get_document_or_dict(change):
    return change.get_document() or {}


def _domain_for_change(change):
    return change.metadata.domain if change.metadata else _get_document_or_dict(change).get('domain')


def _doc_type_for_change(change):
    return change.metadata.document_type if change.metadata else _get_document_or_dict(change).get('doc_type')


class MVPFormIndicatorProcessor(MVPIndicatorProcessorBase):
    document_class = XFormInstance
    indicator_class = IndicatorXForm

    def process_indicators(self, namespaces, domain, doc_dict):
        process_indicators_for_form(namespaces, domain, doc_dict)


def process_indicators_for_form(namespaces, domain, doc_dict):
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
            form_indicator_defs, logger=pillow_logging,
            save_on_update=False
        )
        indicator_form.save()
    except Exception as e:
        pillow_logging.error(
            "Error creating for MVP Indicator for form %(form_id)s: "
            "%(error)s" % {
                'form_id': doc_dict['_id'],
                'error': e,
            },
        )
        raise


class MVPCaseIndicatorProcessor(MVPIndicatorProcessorBase):
    document_class = CommCareCase
    indicator_class = IndicatorCase

    def process_indicators(self, namespaces, domain, doc_dict):
        process_indicators_for_case(namespaces, domain, doc_dict)


def process_indicators_for_case(namespaces, domain, doc_dict):
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
            case_indicator_defs, logger=pillow_logging,
            save_on_update=False
        )
        indicator_case.save()
    except Exception as e:
        pillow_logging.error(
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
                pillow_logging.error(
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
            logger=pillow_logging,
            save_on_update=False
        )
        xform_doc.save()


def get_form_indicators(namespaces, domain, xmlns):
    return [
        indicator for namespace in namespaces
        for indicator in FormIndicatorDefinition.get_all(namespace, domain, xmlns=xmlns)
    ]


def get_mvp_form_indicator_pillow(pillow_id='MVPFormIndicatorPillow'):
    return _get_mvp_indicator_pillow(pillow_id, MVPFormIndicatorProcessor())


def get_mvp_case_indicator_pillow(pillow_id='MVPCaseIndicatorPillow'):
    return _get_mvp_indicator_pillow(pillow_id, MVPCaseIndicatorProcessor())


def _get_mvp_indicator_pillow(pillow_id, processor):
    feed = CouchChangeFeed(
        XFormInstance.get_db(),
        couch_filter='hqadmin/domains_and_doc_types',
        extra_couch_view_params={
            'domains': ' '.join(processor.domains),
            'doc_types': ' '.join(processor.doc_types),
        }
    )
    checkpoint = PillowCheckpoint(
        'mvp_docs.pillows.{}.{}'.format(pillow_id, get_machine_id()), feed.sequence_format
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=feed,
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100
        ),
    )
