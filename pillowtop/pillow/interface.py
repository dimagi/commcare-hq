from abc import ABCMeta, abstractproperty, abstractmethod
from pillowtop.logger import pillow_logging


class PillowBase(object):
    """
    This defines the external pillowtop API. Everything else should be considered a specialization
    on top of it.
    """
    __metaclass__ = ABCMeta

    changes_seen = 0  # a rolling count of how many changes have been seen by the pillow

    @abstractproperty
    def document_store(self):
        """
        Returns a DocumentStore instance for retreiving documents.
        """
        pass

    @abstractproperty
    def checkpoint(self):
        """
        Returns a PillowtopCheckpoint instance dealing with checkpoints.
        """
        pass

    @abstractmethod
    def get_change_feed(self):
        """
        Returns a ChangeFeed instance for iterating changes.
        """
        pass

    def get_checkpoint(self, verify_unchanged=False):
        return self.checkpoint.get_or_create(verify_unchanged=verify_unchanged)

    def set_checkpoint(self, change):
        pillow_logging.info(
            "(%s) setting checkpoint: %s" % (self.checkpoint.checkpoint_id, change['seq'])
        )
        self.checkpoint.update_to(change['seq'])

    def reset_checkpoint(self):
        self.checkpoint.reset_checkpoint()
