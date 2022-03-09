from abc import ABCMeta, abstractmethod

from memoized import memoized


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
