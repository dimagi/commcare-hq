from abc import ABCMeta, abstractmethod


class ChangeProvider(object):
    """
    `ChangeProvider`s are used in reindexing. They should support querying the complete
    data set backing a particular `ChangeFeed` object, but are intentionally decoupled
    from `ChangeFeed`s.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def iter_all_changes(self, start_from=None):
        pass
