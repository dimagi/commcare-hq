from abc import ABCMeta, abstractmethod
from collections import namedtuple
import six


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


class LedgerDBInterface(six.with_metaclass(ABCMeta, object)):
    """
    A very lightweight in-memory processing DB for ledgers, modeled after the CaseDb.

    This allows you to do multiple in-memory transactional updates on a single form
    without committing them to the database.
    """

    def __init__(self):
        self._balances = {}
        self._ledgers = {}

    def get_ledger(self, unique_ledger_reference):
        if unique_ledger_reference not in self._ledgers:
            ledger = self._get_ledger(unique_ledger_reference)
            self._ledgers[unique_ledger_reference] = ledger
        return self._ledgers[unique_ledger_reference]

    def set_ledger(self, ledger):
        # if it's not there or the value is None
        if not self._ledgers.get(ledger.ledger_reference, None):
            self._ledgers[ledger.ledger_reference] = ledger

    def get_current_ledger_value(self, unique_ledger_reference):
        ledger = self.get_ledger(unique_ledger_reference)
        return ledger.stock_on_hand if ledger else 0

    @abstractmethod
    def get_ledgers_for_case(self, case_id):
        pass

    @abstractmethod
    def _get_ledger(self, unique_ledger_reference):
        pass


class LedgerProcessorInterface(six.with_metaclass(ABCMeta, object)):
    def __init__(self, domain):
        self.domain = domain

    @abstractmethod
    def get_models_to_update(self, form_id, stock_report_helpers, deprecated_helpers, ledger_db=None):
        """
        Returns a list of StockModelUpdate object containing everything that needs to be updated.
        """
        pass

    @abstractmethod
    def rebuild_ledger_state(self, case_id, section_id, entry_id):
        pass

    @abstractmethod
    def process_form_archived(self, form):
        pass

    @abstractmethod
    def process_form_unarchived(self, form):
        pass
