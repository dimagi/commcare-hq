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


class LedgerProcessorInterface(object):
    __metaclass__ = ABCMeta

    def __init__(self, domain):
        self.domain = domain

    @abstractmethod
    def get_models_to_update(self, stock_report_helper):
        """
        Returns a list of StockModelUpdate object containing everything that needs to be updated.
        """
        pass

    @abstractmethod
    def delete_models_for_stock_report_helper(self, stock_report_helper):
        pass

    @abstractmethod
    def get_ledgers_for_case(self, case_id):
        pass
