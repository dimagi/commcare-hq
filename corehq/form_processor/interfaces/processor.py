import logging
import re
from collections import namedtuple

from couchdbkit.exceptions import BulkSaveError
from redis.exceptions import RedisError

from casexml.apps.case import const
from corehq.form_processor.exceptions import (
    KafkaPublishingError,
    PostSaveError,
    XFormLockError,
    XFormQuestionValueNotFound,
)
from memoized import memoized
from ..models import XFormInstance
from ..system_action import system_action


class CaseUpdateMetadata(namedtuple('CaseUpdateMetadata',
        ['case', 'is_creation', 'previous_owner_id', 'actions'])):
    def merge(self, other):
        return CaseUpdateMetadata(
            case=self.case,
            is_creation=self.is_creation or other.is_creation,
            previous_owner_id=self.previous_owner_id,
            actions=self.actions | other.actions
        )

    @property
    def index_change(self):
        return const.CASE_ACTION_INDEX in self.actions or const.CASE_ACTION_REBUILD in self.actions


ProcessedForms = namedtuple('ProcessedForms', ['submitted', 'deprecated'])
HARD_DELETE_CASE_AND_FORMS = "hard_delete_case_and_forms"


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
        return XFormInstance

    @property
    @memoized
    def processor(self):
        from corehq.form_processor.backends.sql.processor import FormProcessorSQL
        return FormProcessorSQL

    @property
    @memoized
    def casedb_cache(self):
        from corehq.form_processor.backends.sql.casedb import CaseDbCacheSQL
        return CaseDbCacheSQL

    @property
    @memoized
    def ledger_processor(self):
        from corehq.form_processor.backends.sql.ledger import LedgerProcessorSQL
        return LedgerProcessorSQL(domain=self.domain)

    @property
    @memoized
    def ledger_db(self):
        from corehq.form_processor.backends.sql.ledger import LedgerDBSQL
        return LedgerDBSQL()

    def acquire_lock_for_xform(self, xform_id):
        lock = self.xform_model.get_obj_lock_by_id(xform_id, timeout_seconds=15 * 60)
        try:
            if not lock.acquire(blocking=False):
                raise XFormLockError(xform_id)
        except RedisError:
            logging.warning('Redis error when locking %s, continuing with no lock', xform_id)
            lock = None
        return lock

    def get_case_forms(self, case_id):
        return self.processor.get_case_forms(case_id)

    def form_has_case_transactions(self, form_id):
        return self.processor.form_has_case_transactions(form_id)

    def store_attachments(self, xform, attachments):
        """
        Takes a list of Attachment namedtuples with content, name, and content_type and stores them to the XForm
        """
        return self.processor.store_attachments(xform, attachments)

    def copy_attachments(self, from_form, to_form):
        """Copy attachments from one for to another (exlucding form.xml)"""
        self.processor.copy_attachments(from_form, to_form)

    def copy_form_operations(self, from_form, to_form):
        """Copy form operations from one for to another. This happens when a form is edited to ensure
        that the most recent form has the full history."""
        self.processor.copy_form_operations(from_form, to_form)

    def is_duplicate(self, xform_id, domain=None):
        """
        Check if there is already a form with the given ID. If domain is specified only check for
        duplicates within that domain.
        """
        return self.processor.is_duplicate(xform_id, domain=domain)

    def new_xform(self, form_json):
        return self.processor.new_xform(form_json)

    def xformerror_from_xform_instance(self, instance, error_message, with_new_id=False):
        return self.processor.xformerror_from_xform_instance(instance, error_message, with_new_id=with_new_id)

    def update_responses(self, xform, value_responses_map, user_id):
        """
        Update a set of question responses. Returns a list of any
        questions that were not found in the xform.
        """
        from corehq.form_processor.utils.xform import update_response

        errors = []
        xml = xform.get_xml_element()
        for question, response in value_responses_map.items():
            try:
                update_response(xml, question, response, xmlns=xform.xmlns)
            except XFormQuestionValueNotFound:
                errors.append(question)

        existing_form = XFormInstance.objects.get_with_attachments(xform.get_id, xform.domain)
        existing_form, new_form = self.processor.new_form_from_old(existing_form, xml,
                                                                   value_responses_map, user_id)
        self.save_processed_models([new_form, existing_form])

        return errors

    def save_processed_models(self, forms, cases=None, stock_result=None):
        forms = _list_to_processed_forms_tuple(forms)
        if stock_result:
            assert stock_result.populated
        try:
            return self.processor.save_processed_models(
                forms,
                cases=cases,
                stock_result=stock_result,
            )
        except BulkSaveError as e:
            logging.exception('BulkSaveError saving forms', extra={'details': {'errors': e.errors}})
            raise
        except KafkaPublishingError as e:
            from corehq.form_processor.submission_post import notify_submission_error
            notify_submission_error(forms.submitted, 'Error publishing to Kafka')
            raise PostSaveError(e)
        except Exception as e:
            from corehq.form_processor.submission_post import handle_unexpected_error
            instance = forms.submitted
            if forms.deprecated:
                # since this is a form edit there will already be a form with the ID so we need to give this one
                # a new ID
                instance = self.xformerror_from_xform_instance(instance, '', with_new_id=True)
            handle_unexpected_error(self, instance, e)
            e.sentry_capture = False  # we've already notified
            raise

    def hard_delete_case_and_forms(self, case, xforms):
        assert case.domain == self.domain, (case.domain, self.domain)
        args = [case, xforms]
        args_json = [case.case_id, [f.form_id for f in xforms]]
        system_action.submit(HARD_DELETE_CASE_AND_FORMS, args, args_json, self.domain)

    @system_action(HARD_DELETE_CASE_AND_FORMS)
    def _hard_delete_case_and_forms(case, xforms):
        domain = case.domain
        all_domains = {domain} | {xform.domain for xform in xforms}
        assert len(all_domains) == 1, all_domains
        processor = FormProcessorInterface(domain).processor
        processor.hard_delete_case_and_forms(domain, case, xforms)

    def apply_deprecation(self, existing_xform, new_xform):
        return self.processor.apply_deprecation(existing_xform, new_xform)

    def deduplicate_xform(self, xform):
        return self.processor.deduplicate_xform(xform)

    def assign_new_id(self, xform):
        return self.processor.assign_new_id(xform)

    def hard_rebuild_case(self, case_id, detail, lock=True):
        return self.processor.hard_rebuild_case(self.domain, case_id, detail, lock=lock)

    def get_cases_from_forms(self, case_db, xforms):
        """
        Returns a dict of case_ids to CaseUpdateMetadata objects containing the touched cases
        (with the forms' updates already applied to the cases)
        """
        return self.processor.get_cases_from_forms(case_db, xforms)

    def submission_error_form_instance(self, instance, message):
        return self.processor.submission_error_form_instance(self.domain, instance, message)

    def get_case_with_lock(self, case_id, lock=False, wrap=False):
        """
        Get a case with option lock. If case not found in domains DB also check other DB
        and raise IllegalCaseId if found.

        :param case_id: ID of case to fetch
        :param lock: Get a Redis lock for the case. Returns None if False or case not found.
        :param wrap: Return wrapped case if True. (Couch only)
        :return: tuple(case, lock). Either could be None
        :raises: IllegalCaseId
        """
        return self.processor.get_case_with_lock(case_id, lock, wrap)


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


class XFormQuestionValueIterator(object):
    """
    Iterator to help navigate a data structure (likely xml or json)
    representing a form submission, based on a given path. Skips root node.
    Each call of `next` returns a tuple of id and index. Iterates until
    the last non-leaf node. After iterating, the leaf node's id is
    available via `last`. Example:

    i = XFormQuestionValueIterator("/data/group/repeat_group[2]/question_id")
    i.next()    # ('group', None)
    i.next()    # ('repeat_group', 1)
    i.next()    # raises StopIteration
    i.last()    # 'question_id'

    Note that repeat groups in the given path are ONE-indexed as in xpath, while
    the indices returned by next/last are ZERO-indexed for easier array indexing.

    Also note that repeat groups have an index only if there are multiple instances
    of the group. This matches the structure of form_data, which uses a list of dicts
    to represent multiple repeat groups but a single dict to represent a single repeat.
    """

    def __init__(self, path):
        path = re.sub(r'^/[^\/]+/', '', path)   # strip root
        self.levels = path.split("/")
        self.levels.reverse()
        self._last = None

    def __iter__(self):
        return self

    def __next__(self):
        if len(self.levels) > 1:
            return self._next()
        raise StopIteration

    def _next(self):
        # Match an identifier (likely a case property or question id)
        # optionally followed by a repeat group index
        (qid, index) = re.match(r'([^[]+)(?:\[(\d+)])?', self.levels.pop()).groups()
        if index is not None:
            index = int(index) - 1
        return (qid, index)

    def last(self):
        if self._last is None and len(self.levels) == 1:
            self._last = self._next()[0]
        return self._last

    next = __next__     # For Py2 compatibility
