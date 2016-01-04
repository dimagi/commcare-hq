from abc import ABCMeta, abstractmethod
from collections import namedtuple


class StockModelUpdateResult(namedtuple('StockModelUpdate', ['to_save', 'to_delete'])):
    """
    to_save should be an iterable of anything with a .save() function (typically django objects)

    to_delete should be an iterable of anything with a .delete() function (typically django objects or querysets)
    """
    def __new__(cls, to_save=None, to_delete=None):
        # http://stackoverflow.com/a/16721002/8207
        return super(StockModelUpdateResult, cls).__new__(
            cls,
            to_save=to_save or [],
            to_delete=to_delete or [],
        )

    def commit(self):
        for to_save in self.to_save:
            to_save.save()
        for to_delete in self.to_delete:
            to_delete.delete()


class LedgerDB(object):
    """
    A very lightweight in-memory processing DB for ledgers, modeled after the CaseDb.

    This allows you to do multiple in-memory transactional updates on a single form
    without committing them to the database.
    """

    def __init__(self, processor):
        self._balances = {}
        self._processor = processor

    def get_current_balance(self, unique_ledger_reference):
        if unique_ledger_reference not in self._balances:
            current_balance = self._processor.get_current_ledger_value(unique_ledger_reference)
            self._balances[unique_ledger_reference] = current_balance
        return self._balances[unique_ledger_reference]

    def set_current_balance(self, unique_ledger_reference, balance):
        self._balances[unique_ledger_reference] = balance


class LedgerProcessorInterface(object):
    __metaclass__ = ABCMeta

    def __init__(self, domain):
        self.domain = domain

    @abstractmethod
    def get_models_to_update(self, stock_report_helper, ledger_db=None):
        """
        Returns a list of StockModelUpdate object containing everything that needs to be updated.
        """
        pass

    @abstractmethod
    def get_ledgers_for_case(self, case_id):
        pass

    @abstractmethod
    def get_current_ledger_value(self, unique_ledger_reference):
        pass
