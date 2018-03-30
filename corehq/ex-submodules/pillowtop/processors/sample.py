from __future__ import absolute_import
from __future__ import unicode_literals
from pillowtop.logger import pillow_logging
from pillowtop.processors.interface import PillowProcessor


class NoopProcessor(PillowProcessor):
    """
    Processor that does absolutely nothing.
    """

    def process_change(self, pillow_instance, change):
        pass


class LoggingProcessor(PillowProcessor):
    """
    Processor that just logs things - useful in tests or debugging.
    """

    def __init__(self, logger=None):
        self.logger = logger or pillow_logging

    def process_change(self, pillow_instance, change):
        self.logger.info(change)


class CountingProcessor(PillowProcessor):
    """
    Processor that just counts how many things it has processed
    """

    def __init__(self):
        self.count = 0

    def process_change(self, pillow_instance, change):
        self.count += 1


class TestProcessor(PillowProcessor):
    """
    Processor that just keeps the change in an in-memory list for testing
    """

    def __init__(self):
        self.changes_seen = []

    def process_change(self, pillow_instance, change):
        self.changes_seen.append(change)
