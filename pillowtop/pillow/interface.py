from abc import ABCMeta, abstractproperty, abstractmethod


class PillowBase(object):
    """
    This defines the external pillowtop API. Everything else should be considered a specialization
    on top of it.
    """
    __metaclass__ = ABCMeta

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

    def reset_checkpoint(self):
        self.checkpoint.reset_checkpoint()
