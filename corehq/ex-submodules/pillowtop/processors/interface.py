from __future__ import absolute_import
from abc import ABCMeta, abstractmethod
import six


class PillowProcessor(six.with_metaclass(ABCMeta, object)):
    supports_batch_processing = False

    @abstractmethod
    def process_change(self, pillow_instance, change):
        pass

    def checkpoint_updated(self):
        pass


class BulkPillowProcessor(PillowProcessor):
    # To make the pillow process in chunks, create and use a processor
    #   that extends this class.

    supports_batch_processing = True

    @abstractmethod
    def process_changes_chunk(self, pillow_instance, changes_chunk):
        pass
