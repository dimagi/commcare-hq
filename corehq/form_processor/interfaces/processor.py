from collections import namedtuple
import logging

from couchdbkit.exceptions import BulkSaveError
from redis.exceptions import RedisError

from dimagi.utils.decorators.memoized import memoized

from ..utils import should_use_sql_backend


CaseUpdateMetadata = namedtuple('CaseUpdateMetadata', ['case', 'is_creation', 'previous_owner_id'])
ProcessedForms = namedtuple('ProcessedForms', ['submitted', 'deprecated'])


class FormProcessorInterface(object):
    """
    The FormProcessorInterface serves as the base transactions that take place in forms. Different
    backends can implement this class in order to make common interface.
    """

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def xform_model(self):
        from couchforms.models import XFormInstance
        from corehq.form_processor.models import XFormInstanceSQL

        if should_use_sql_backend(self.domain):
            return XFormInstanceSQL
        else:
            return XFormInstance

    @property
    @memoized
    def sync_log_model(self):
        from casexml.apps.phone.models import SyncLog

        if should_use_sql_backend(self.domain):
            return SyncLog
        else:
            return SyncLog

    @property
    @memoized
    def processor(self):
        from corehq.form_processor.backends.couch.processor import FormProcessorCouch
        from corehq.form_processor.backends.sql.processor import FormProcessorSQL

        if should_use_sql_backend(self.domain):
            return FormProcessorSQL
        else:
            return FormProcessorCouch

    @property
    @memoized
    def casedb_cache(self):
        from corehq.form_processor.backends.couch.casedb import CaseDbCacheCouch
        from corehq.form_processor.backends.sql.casedb import CaseDbCacheSQL

        if should_use_sql_backend(self.domain):
            return CaseDbCacheSQL
        else:
            return CaseDbCacheCouch

    @property
    @memoized
    def ledger_processor(self):
        from corehq.form_processor.backends.couch.ledger import LedgerProcessorCouch
        from corehq.form_processor.backends.sql.ledger import LedgerProcessorSQL
        if should_use_sql_backend(self.domain):
            return LedgerProcessorSQL(domain=self.domain)
        else:
            return LedgerProcessorCouch(domain=self.domain)

    def save_xform(self, xform):
        return self.processor.save_xform(xform)

    def acquire_lock_for_xform(self, xform_id):
        lock = self.xform_model.get_obj_lock_by_id(xform_id, timeout_seconds=2 * 60)
        try:
            lock.acquire()
        except RedisError:
            lock = None
        return lock

    def get_case_forms(self, case_id):
        return self.processor.get_case_forms(case_id)

    def store_attachments(self, xform, attachments):
        """
        Takes a list of Attachment namedtuples with content, name, and content_type and stores them to the XForm
        """
        return self.processor.store_attachments(xform, attachments)

    def is_duplicate(self, xform_id, domain=None):
        """
        Check if there is already a form with the given ID. If domain is specified only check for
        duplicates within that domain.
        """
        return self.processor.is_duplicate(xform_id, domain=domain)

    def new_xform(self, instance_xml):
        return self.processor.new_xform(instance_xml)

    def xformerror_from_xform_instance(self, instance, error_message, with_new_id=False):
        return self.processor.xformerror_from_xform_instance(instance, error_message, with_new_id=with_new_id)

    def save_processed_models(self, forms, cases=None, stock_updates=None):
        forms = _list_to_processed_forms_tuple(forms)
        try:
            return self.processor.save_processed_models(
                forms,
                cases=cases,
                stock_updates=stock_updates,
            )
        except BulkSaveError as e:
            logging.error('BulkSaveError saving forms', exc_info=1,
                          extra={'details': {'errors': e.errors}})
            raise
        except Exception as e:
            xforms_being_saved = [form.form_id for form in forms if form]
            error_message = u'Unexpected error bulk saving docs {}: {}, doc_ids: {}'.format(
                type(e).__name__,
                unicode(e),
                ', '.join(xforms_being_saved)
            )
            from corehq.form_processor.submission_post import handle_unexpected_error
            handle_unexpected_error(self, forms.submitted, error_message)
            raise

    def hard_delete_case_and_forms(self, case, xforms):
        domain = case.domain
        all_domains = {domain} | {xform.domain for xform in xforms}
        assert len(all_domains) == 1, all_domains
        self.processor.hard_delete_case_and_forms(domain, case, xforms)

    def apply_deprecation(self, existing_xform, new_xform):
        return self.processor.apply_deprecation(existing_xform, new_xform)

    def deduplicate_xform(self, xform):
        return self.processor.deduplicate_xform(xform)

    def assign_new_id(self, xform):
        return self.processor.assign_new_id(xform)

    def hard_rebuild_case(self, case_id, detail):
        return self.processor.hard_rebuild_case(self.domain, case_id, detail)

    def get_cases_from_forms(self, xforms, case_db):
        """
        Returns a dict of case_ids to CaseUpdateMetadata objects containing the touched cases
        (with the forms' updates already applied to the cases)
        """
        return self.processor.get_cases_from_forms(xforms, case_db)

    def submission_error_form_instance(self, instance, message):
        return self.processor.submission_error_form_instance(self.domain, instance, message)


def _list_to_processed_forms_tuple(forms):
    """
    :param forms: List of forms (either 1 or 2)
    :return: tuple with main form first and deprecated form second
    """
    if len(forms) == 1:
        return ProcessedForms(forms[0], None)
    else:
        assert len(forms) == 2
        return ProcessedForms(*sorted(forms, key=lambda form: form.is_deprecated))
