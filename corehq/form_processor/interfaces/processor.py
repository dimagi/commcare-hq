import logging

from couchdbkit.exceptions import BulkSaveError

from dimagi.utils.decorators.memoized import memoized
from corehq.util.test_utils import unit_testing_only
from casexml.apps.case.util import post_case_blocks

from ..utils import should_use_sql_backend


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
    def case_model(self):
        from casexml.apps.case.models import CommCareCase
        from corehq.form_processor.models import CommCareCaseSQL
        if should_use_sql_backend(self.domain):
            return CommCareCaseSQL
        else:
            return CommCareCase

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

    @unit_testing_only
    def post_xform(self, instance_xml, attachments=None, process=None, domain='test-domain'):
        return self.processor.post_xform(instance_xml, attachments=attachments, process=process, domain=domain)

    def submit_form_locally(self, instance, domain='test-domain', **kwargs):
        from corehq.apps.receiverwrapper.util import submit_form_locally
        return submit_form_locally(instance, domain, **kwargs)

    def post_case_blocks(self, case_blocks, form_extras=None, domain=None):
        return post_case_blocks(case_blocks, form_extras=form_extras, domain=domain)

    def store_attachments(self, xform, attachments):
        """
        Takes a list of Attachment namedtuples with content, name, and content_type and stores them to the XForm
        """
        return self.processor.store_attachments(xform, attachments)

    def is_duplicate(self, xform):
        return self.processor.is_duplicate(xform)

    def new_xform(self, instance_xml):
        return self.processor.new_xform(instance_xml)

    def xformerror_from_xform_instance(self, instance, error_message, with_new_id=False):
        return self.processor.xformerror_from_xform_instance(instance, error_message, with_new_id=with_new_id)

    def bulk_save(self, instance, xforms, cases=None):
        try:
            return self.processor.bulk_save(instance, xforms, cases=cases)
        except BulkSaveError as e:
            logging.error('BulkSaveError saving forms', exc_info=1,
                          extra={'details': {'errors': e.errors}})
            raise
        except Exception as e:
            from couchforms.util import _handle_unexpected_error
            xforms_being_saved = [xform.form_id for xform in xforms]
            error_message = u'Unexpected error bulk saving docs {}: {}, doc_ids: {}'.format(
                type(e).__name__,
                unicode(e),
                ', '.join(xforms_being_saved)
            )
            _handle_unexpected_error(self, instance, error_message)
            raise

    def process_stock(self, xforms, case_db):
        return self.processor.process_stock(xforms, case_db)

    def deprecate_xform(self, existing_xform, new_xform):
        return self.processor.deprecate_xform(existing_xform, new_xform)

    def deduplicate_xform(self, xform):
        return self.processor.deduplicate_xform(xform)

    def should_handle_as_duplicate_or_edit(self, xform_id, domain):
        return self.processor.should_handle_as_duplicate_or_edit(xform_id, domain)

    def assign_new_id(self, xform):
        return self.processor.assign_new_id(xform)
