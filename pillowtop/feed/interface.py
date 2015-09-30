from abc import ABCMeta, abstractmethod


class Change(object):
    """
    A record of a change. Provides a dict-like interface for backwards compatibility with couch changes.
    """
    def __init__(self, id, sequence_id, document=None, deleted=False):
        self.id = id
        self.sequence_id = sequence_id
        self.document = document
        self.deleted = deleted
        self._dict = {
            'id': self.id,
            'seq': self.sequence_id,
            'doc': self.document,
            'deleted': self.deleted,
        }

    def __len__(self):
        return len(self._dict)

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        raise NotImplemented('This is a read-only dictionary!')

    def __delitem__(self, key, value):
        raise NotImplemented('This is a read-only dictionary!')

    def __iter__(self):
        return iter(self._dict)

    def __contains__(self, item):
        return item in self._dict

    def get(self, key, default):
        return self._dict.get(key, default)

    def pop(self, key, default):
        raise NotImplemented('This is a read-only dictionary!')


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
