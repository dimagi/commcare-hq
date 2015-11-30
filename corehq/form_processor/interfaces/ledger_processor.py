from abc import ABCMeta, abstractmethod


class LedgerProcessorInterface(object):
    __metaclass__ = ABCMeta

    def __init__(self, domain):
        self.domain = domain

    @abstractmethod
    def create_models_for_stock_report_helper(self, stock_report_helper):
        pass

    @abstractmethod
    def delete_models_for_stock_report_helper(self, stock_report_helper):
        pass
