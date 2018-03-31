from __future__ import absolute_import
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod
import six


class ChangeProvider(six.with_metaclass(ABCMeta, object)):
    """
    `ChangeProvider`s are used in reindexing. They should support querying the complete
    data set backing a particular `ChangeFeed` object, but are intentionally decoupled
    from `ChangeFeed`s.
    """

    @abstractmethod
    def iter_all_changes(self, start_from=None):
        pass
