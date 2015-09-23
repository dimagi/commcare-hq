from abc import ABCMeta, abstractmethod


class Change(object):

    def __init__(self, id, sequence_id, document=None, deleted=False):
        self.id = id
        self.sequence_id = sequence_id
        self.document = document
        self.deleted = deleted

    def to_legacy_dict(self):
        return {
            'id': self.id,
            'seq': self.sequence_id,
            'doc': self.document,
            'deleted': self.deleted,
        }


class ChangeFeed(object):
    """
    Basic change feed API.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def iter_changes(self, since, forever):
        """
        Iterates through all changes since a certain sequence ID.
        """
        pass
