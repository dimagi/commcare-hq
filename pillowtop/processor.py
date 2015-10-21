from abc import ABCMeta, abstractmethod
from pillowtop.logger import pillow_logging


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change, do_set_checkpoint):
        pass


class LoggingProcessor(PillowProcessor):
    """
    Processor that just logs things - useful in tests or debugging.
    """
    def process_change(self, pillow_instance, change, do_set_checkpoint):
        pillow_logging.info(change)
