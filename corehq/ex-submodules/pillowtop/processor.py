from abc import ABCMeta, abstractmethod
from pillowtop.logger import pillow_logging


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change, do_set_checkpoint):
        pass


class NoopProcessor(PillowProcessor):
    """
    Processor that does absolutely nothing.
    """
    def process_change(self, pillow_instance, change, do_set_checkpoint):
        pass


class LoggingProcessor(PillowProcessor):
    """
    Processor that just logs things - useful in tests or debugging.
    """
    def __init__(self, logger=None):
        self.logger = logger or pillow_logging

    def process_change(self, pillow_instance, change, do_set_checkpoint):
        self.logger.info(change)
