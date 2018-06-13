from __future__ import absolute_import
from abc import ABCMeta, abstractmethod
import six


class PillowProcessor(six.with_metaclass(ABCMeta, object)):
    @abstractmethod
    def process_change(self, pillow_instance, change):
        pass

    def checkpoint_updated(self):
        pass


class BulkPillowProcessor(PillowProcessor):
    # To make the pillow process in chunks, create and use a processor
    #   that extends this class.

    # If `processor_chunk_size` is set to zero, pillow won't process in chunks
    processor_chunk_size = 0

    @abstractmethod
    def process_changes_chunk(self, pillow_instance, changes_chunk):
        pass


class BulkProcessingResult(object):
    def __init__(self, succeeded_changes, failed_changes):
        self.succeeded_changes = succeeded_changes
        self.failed_changes = failed_changes
