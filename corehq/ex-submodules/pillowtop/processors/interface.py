from abc import ABCMeta, abstractmethod
import six


class PillowProcessor(six.with_metaclass(ABCMeta, object)):
    supports_batch_processing = False

    @abstractmethod
    def process_change(self, change):
        pass

    def checkpoint_updated(self):
        pass


class BulkPillowProcessor(PillowProcessor):
    # To make the pillow process in chunks, create and use a processor
    #   that extends this class.

    supports_batch_processing = True

    @abstractmethod
    def process_changes_chunk(self, changes_chunk):
        """
        Should process given changes_chunk.

            Must return a tuple with first element as set of failed changes that
            should be reprocessed serially by pillow and second element as a list
            of (change, exception) tuples for failed changes that should not be
            reprocessed but for which exceptions are to be handled by handle_pillow_error
        """
        pass
