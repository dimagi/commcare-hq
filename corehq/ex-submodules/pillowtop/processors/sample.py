from pillowtop.logger import pillow_logging
from pillowtop.processors.interface import PillowProcessor


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
