from abc import ABCMeta, abstractmethod
from collections import namedtuple
from warnings import warn

from memoized import memoized
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex


CaseIndexInfo = namedtuple(
    'CaseIndexInfo', ['case_id', 'identifier', 'referenced_id', 'referenced_type', 'relationship']
)


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
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return CommCareCase.objects.get_case(case_id, self.domain)

    def get_cases(self, case_ids, ordered=False, prefetched_indices=None):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_cases(
            case_ids, ordered=ordered, prefetched_indices=prefetched_indices)

    def iter_cases(self, case_ids):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        yield from CommCareCase.objects.iter_cases(case_ids)

    def get_case_ids_that_exist(self, case_ids):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_case_ids_that_exist(self.domain, case_ids)

    def get_case_xform_ids(self, case_id):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_case_xform_ids(case_id)

    def get_case_ids_in_domain(self, type=None):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_case_ids_in_domain(self.domain, type)

    def get_case_ids_by_owners(self, owner_ids, closed=None):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_case_ids_in_domain_by_owners(self.domain, owner_ids, closed=closed)

    def get_open_case_ids_in_domain_by_type(self, case_type, owner_ids=None):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_open_case_ids_in_domain_by_type(self.domain, case_type, owner_ids)

    def get_related_indices(self, case_ids, exclude_indices):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_related_indices(self.domain, case_ids, exclude_indices)

    def get_closed_and_deleted_ids(self, case_ids):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_closed_and_deleted_ids(self.domain, case_ids)

    def get_modified_case_ids(self, case_ids, sync_log):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_modified_case_ids(self, case_ids, sync_log)

    def get_extension_case_ids(self, case_ids, exclude_for_case_type=None):
        warn("DEPRECATED use CommCareCaseIndex.objects", DeprecationWarning)
        return self.db_accessor.get_extension_case_ids(
            self.domain, case_ids, exclude_for_case_type=exclude_for_case_type)

    def get_last_modified_dates(self, case_ids):
        return self.db_accessor.get_last_modified_dates(self.domain, case_ids)

    def get_all_reverse_indices_info(self, case_ids):
        warn("DEPRECATED use CommCareCaseIndex.objects", DeprecationWarning)
        return self.db_accessor.get_all_reverse_indices_info(self.domain, case_ids)

    def get_reverse_indexed_cases(self, case_ids, case_types=None, is_closed=None):
        warn("DEPRECATED use CommCareCaseIndex.objects", DeprecationWarning)
        return self.db_accessor.get_reverse_indexed_cases(self.domain, case_ids, case_types, is_closed)

    def get_attachment_content(self, case_id, attachment_id):
        warn("DEPRECATED use CaseAttachment.get_content", DeprecationWarning)
        return self.db_accessor.get_attachment_content(case_id, attachment_id)

    def get_case_by_domain_hq_user_id(self, user_id, case_type):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_case_by_domain_hq_user_id(self.domain, user_id, case_type)

    def get_cases_by_external_id(self, external_id, case_type=None):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_cases_by_external_id(self.domain, external_id, case_type)

    def soft_delete_cases(self, case_ids, deletion_date=None, deletion_id=None):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.soft_delete_cases(self.domain, case_ids, deletion_date, deletion_id)

    def soft_undelete_cases(self, case_ids):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.soft_undelete_cases(self.domain, case_ids)

    def get_deleted_case_ids_by_owner(self, owner_id):
        warn("DEPRECATED use CommCareCase.objects", DeprecationWarning)
        return self.db_accessor.get_deleted_case_ids_by_owner(self.domain, owner_id)

    def get_extension_chain(self, case_ids, include_closed=True, exclude_for_case_type=None):
        warn("DEPRECATED use CommCareCaseIndex.objects", DeprecationWarning)
        return CommCareCaseIndex.objects.get_extension_chain(
            self.domain, case_ids, include_closed, exclude_for_case_type)

    def get_case_owner_ids(self):
        return self.db_accessor.get_case_owner_ids(self.domain)


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
