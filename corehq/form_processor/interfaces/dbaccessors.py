from abc import ABCMeta, abstractmethod
from collections import namedtuple
from io import BytesIO

from memoized import memoized

from dimagi.utils.chunked import chunked

from ..exceptions import CaseNotFound
from ..models import XFormInstance


CaseIndexInfo = namedtuple(
    'CaseIndexInfo', ['case_id', 'identifier', 'referenced_id', 'referenced_type', 'relationship']
)


class FormAccessors:
    """DEPRECATED use XFormInstance.objects"""

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        return FormAccessorSQL

    def get_form(self, form_id):
        """DEPRECATED use XFormInstance.objects"""
        return XFormInstance.objects.get_form(form_id, self.domain)

    def get_forms(self, form_ids, ordered=False):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.get_forms(form_ids, ordered=ordered)

    def iter_forms(self, form_ids):
        """DEPRECATED use XFormInstance.objects"""
        yield from XFormInstance.objects.iter_forms(form_ids)

    def form_exists(self, form_id):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.form_exists(form_id, domain=self.domain)

    def get_all_form_ids_in_domain(self, doc_type='XFormInstance'):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.get_form_ids_in_domain_by_type(self.domain, doc_type)

    def get_forms_by_type(self, type_, limit, recent_first=False):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.get_forms_by_type(self.domain, type_, limit, recent_first)

    def iter_form_ids_by_xmlns(self, xmlns=None):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.iter_form_ids_by_xmlns(self.domain, xmlns)

    def get_with_attachments(self, form_id):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.get_with_attachments(form_id)

    def save_new_form(self, form):
        """DEPRECATED use XFormInstance.objects"""
        self.db_accessor.save_new_form(form)

    def update_form_problem_and_state(self, form):
        """DEPRECATED use XFormInstance.objects"""
        self.db_accessor.update_form_problem_and_state(form)

    def get_deleted_form_ids_for_user(self, user_id):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.get_deleted_form_ids_for_user(self.domain, user_id)

    def get_form_ids_for_user(self, user_id):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.get_form_ids_for_user(self.domain, user_id)

    def get_attachment_content(self, form_id, attachment_name):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.get_attachment_content(form_id, attachment_name)

    @classmethod
    def do_archive(cls, form, archive, user_id, trigger_signals):
        """DEPRECATED use XFormInstance.objects"""
        return XFormInstance.objects.do_archive(form, archive, user_id, trigger_signals)

    @classmethod
    def publish_archive_action_to_kafka(cls, form, user_id, archive):
        """DEPRECATED use XFormInstance.objects"""
        XFormInstance.objects.publish_archive_action_to_kafka(form, user_id, archive)

    def soft_delete_forms(self, form_ids, deletion_date=None, deletion_id=None):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.soft_delete_forms(self.domain, form_ids, deletion_date, deletion_id)

    def soft_undelete_forms(self, form_ids):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.soft_undelete_forms(self.domain, form_ids)

    def modify_attachment_xml_and_metadata(self, form_data, form_attachment_new_xml, new_username):
        """DEPRECATED use XFormInstance.objects"""
        return self.db_accessor.modify_attachment_xml_and_metadata(form_data,
                                                                   form_attachment_new_xml,
                                                                   new_username)


class AbstractCaseAccessor(metaclass=ABCMeta):
    """
    Contract for common methods expected on CaseAccessor(SQL/Couch). All methods
    should be static or classmethods.
    """
    @staticmethod
    @abstractmethod
    def get_case(case_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_cases(case_ids, ordered=False, prefetched_indices=None):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def case_exists(case_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_case_ids_that_exist(domain, case_ids):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_case_xform_ids(case_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_case_ids_in_domain(domain, type=None):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_case_ids_in_domain_by_owners(domain, owner_ids):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_open_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_closed_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_open_case_ids_in_domain_by_type(domain, case_type, owner_ids=None):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_related_indices(case_ids, exclude_indices):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_extension_case_ids(domain, case_ids, include_closed, exclude_for_case_type=None):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_indexed_case_ids(domain, case_ids):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_reverse_indexed_cases(domain, case_ids, case_types=None, is_closed=None):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_last_modified_dates(domain, case_ids):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_all_reverse_indices_info(domain, case_ids):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_attachment_content(case_id, attachment_id):
        """
        :param attachment_id:
        :return: AttachmentContent object
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_case_by_domain_hq_user_id(domain, user_id, case_type):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_cases_by_external_id(domain, external_id, case_type=None):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def soft_delete_cases(domain, case_ids, deletion_date=None, deletion_id=None):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def soft_undelete_cases(domain, case_ids):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_deleted_case_ids_by_owner(domain, owner_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_case_owner_ids(domain):
        raise NotImplementedError


class CaseAccessors(object):
    """
    Facade for Case DB access that proxies method calls to SQL or Couch version
    """

    def __init__(self, domain):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL

    def get_case(self, case_id):
        if not case_id:
            raise CaseNotFound
        case = self.db_accessor.get_case(case_id)
        if case.domain != self.domain:
            raise CaseNotFound(case_id)
        return case

    def get_cases(self, case_ids, ordered=False, prefetched_indices=None):
        return self.db_accessor.get_cases(
            case_ids, ordered=ordered, prefetched_indices=prefetched_indices)

    def iter_cases(self, case_ids):
        for chunk in chunked(case_ids, 100):
            chunk = list([_f for _f in chunk if _f])
            for case in self.get_cases(chunk):
                yield case

    def get_case_ids_that_exist(self, case_ids):
        return self.db_accessor.get_case_ids_that_exist(self.domain, case_ids)

    def get_case_xform_ids(self, case_id):
        return self.db_accessor.get_case_xform_ids(case_id)

    def get_case_ids_in_domain(self, type=None):
        return self.db_accessor.get_case_ids_in_domain(self.domain, type)

    def get_case_ids_by_owners(self, owner_ids, closed=None):
        """
        get case_ids for open, closed, or all cases in a domain
        that belong to a list of owner_ids

        owner_ids: a list of owner ids to filter on.
            A case matches if it belongs to any of them.
        closed: True (only closed cases), False (only open cases), or None (all)

        returns a list of case_ids
        """
        return self.db_accessor.get_case_ids_in_domain_by_owners(self.domain, owner_ids, closed=closed)

    def get_open_case_ids_for_owner(self, owner_id):
        return self.db_accessor.get_open_case_ids_for_owner(self.domain, owner_id)

    def get_open_case_ids_in_domain_by_type(self, case_type, owner_ids=None):
        return self.db_accessor.get_open_case_ids_in_domain_by_type(self.domain, case_type, owner_ids)

    def get_related_indices(self, case_ids, exclude_indices):
        """Get indices (forward and reverse) for the given set of case ids

        :param case_ids: A list of case ids.
        :param exclude_indices: A set or dict of index id strings with
        the format ``'<index.case_id> <index.identifier>'``.
        :returns: A list of CommCareCaseIndex-like objects.
        """
        return self.db_accessor.get_related_indices(self.domain, case_ids, exclude_indices)

    def get_closed_and_deleted_ids(self, case_ids):
        """Get the subset of given list of case ids that are closed or deleted

        :returns: List of three-tuples: `(case_id, closed, deleted)`
        """
        return self.db_accessor.get_closed_and_deleted_ids(self.domain, case_ids)

    def get_modified_case_ids(self, case_ids, sync_log):
        """Get the subset of given list of case ids that have been modified
        since sync date/log id
        """
        return self.db_accessor.get_modified_case_ids(self, case_ids, sync_log)

    def get_extension_case_ids(self, case_ids, exclude_for_case_type=None):
        return self.db_accessor.get_extension_case_ids(
            self.domain, case_ids, exclude_for_case_type=exclude_for_case_type)

    def get_indexed_case_ids(self, case_ids):
        return self.db_accessor.get_indexed_case_ids(self.domain, case_ids)

    def get_last_modified_dates(self, case_ids):
        return self.db_accessor.get_last_modified_dates(self.domain, case_ids)

    def get_closed_case_ids_for_owner(self, owner_id):
        return self.db_accessor.get_closed_case_ids_for_owner(self.domain, owner_id)

    def get_all_reverse_indices_info(self, case_ids):
        return self.db_accessor.get_all_reverse_indices_info(self.domain, case_ids)

    def get_reverse_indexed_cases(self, case_ids, case_types=None, is_closed=None):
        return self.db_accessor.get_reverse_indexed_cases(self.domain, case_ids, case_types, is_closed)

    def get_attachment_content(self, case_id, attachment_id):
        return self.db_accessor.get_attachment_content(case_id, attachment_id)

    def get_case_by_domain_hq_user_id(self, user_id, case_type):
        return self.db_accessor.get_case_by_domain_hq_user_id(self.domain, user_id, case_type)

    def get_cases_by_external_id(self, external_id, case_type=None):
        return self.db_accessor.get_cases_by_external_id(self.domain, external_id, case_type)

    def soft_delete_cases(self, case_ids, deletion_date=None, deletion_id=None):
        return self.db_accessor.soft_delete_cases(self.domain, case_ids, deletion_date, deletion_id)

    def soft_undelete_cases(self, case_ids):
        return self.db_accessor.soft_undelete_cases(self.domain, case_ids)

    def get_deleted_case_ids_by_owner(self, owner_id):
        return self.db_accessor.get_deleted_case_ids_by_owner(self.domain, owner_id)

    def get_extension_chain(self, case_ids, include_closed=True, exclude_for_case_type=None):
        assert isinstance(case_ids, list)
        get_extension_case_ids = self.db_accessor.get_extension_case_ids

        incoming_extensions = set(get_extension_case_ids(
            self.domain, case_ids, include_closed, exclude_for_case_type))
        all_extension_ids = set(incoming_extensions)
        new_extensions = set(incoming_extensions)
        while new_extensions:
            extensions = get_extension_case_ids(
                self.domain, list(new_extensions), include_closed, exclude_for_case_type
            )
            new_extensions = set(extensions) - all_extension_ids
            all_extension_ids = all_extension_ids | new_extensions
        return all_extension_ids

    def get_case_owner_ids(self):
        return self.db_accessor.get_case_owner_ids(self.domain)


def get_cached_case_attachment(domain, case_id, attachment_id, is_image=False):
    attachment_cache_key = "%(case_id)s_%(attachment)s" % {
        "case_id": case_id,
        "attachment": attachment_id
    }

    from dimagi.utils.django.cached_object import CachedObject, CachedImage
    cobject = CachedImage(attachment_cache_key) if is_image else CachedObject(attachment_cache_key)
    if not cobject.is_cached():
        content = CaseAccessors(domain).get_attachment_content(case_id, attachment_id)
        stream = BytesIO(content.content_body)
        metadata = {'content_type': content.content_type}
        cobject.cache_put(stream, metadata)

    return cobject


class AbstractLedgerAccessor(metaclass=ABCMeta):

    @staticmethod
    @abstractmethod
    def get_transactions_for_consumption(domain, case_id, product_id, section_id, window_start, window_end):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_ledger_value(case_id, section_id, entry_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_ledger_transactions_for_case(case_id, section_id=None, entry_id=None):
        """
        :return: List of transactions orderd by date ascending
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_latest_transaction(case_id, section_id, entry_id):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_current_ledger_state(case_ids, ensure_form_id=False):
        """
        Given a list of case IDs return a dict of all current ledger data of the following format:
        {
            case_id: {
                section_id: {
                     product_id: <LedgerValue>,
                     product_id: <LedgerValue>,
                     ...
                },
                ...
            },
            ...
        }
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_ledger_values_for_cases(case_ids, section_ids=None, entry_ids=None, date_start=None, date_end=None):
        raise NotImplementedError


class LedgerAccessors(object):
    """
    Facade for Ledger DB access that proxies method calls to SQL or Couch version
    """

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
        return LedgerAccessorSQL

    def get_transactions_for_consumption(self, case_id, product_id, section_id, window_start, window_end):
        return self.db_accessor.get_transactions_for_consumption(
            self.domain, case_id, product_id, section_id, window_start, window_end
        )

    def get_ledger_value(self, case_id, section_id, entry_id):
        return self.db_accessor.get_ledger_value(case_id, section_id, entry_id)

    def get_ledger_transactions_for_case(self, case_id, section_id=None, entry_id=None):
        return self.db_accessor.get_ledger_transactions_for_case(case_id, section_id, entry_id)

    def get_latest_transaction(self, case_id, section_id, entry_id):
        return self.db_accessor.get_latest_transaction(case_id, section_id, entry_id)

    def get_ledger_values_for_case(self, case_id):
        return self.db_accessor.get_ledger_values_for_case(case_id)

    def get_current_ledger_state(self, case_ids):
        if not case_ids:
            return {}
        return self.db_accessor.get_current_ledger_state(case_ids)

    def get_case_ledger_state(self, case_id, ensure_form_id=False):
        return self.db_accessor.get_current_ledger_state([case_id], ensure_form_id=ensure_form_id)[case_id]

    def get_ledger_values_for_cases(self,
            case_ids, section_ids=None, entry_ids=None, date_start=None, date_end=None):
        return self.db_accessor.get_ledger_values_for_cases(case_ids, section_ids, entry_ids, date_start, date_end)
