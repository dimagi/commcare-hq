import abc
from collections import namedtuple


class ListApi(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_list(self, start_index=0):
        pass

    def get_all(self):
        start_index = 0
        while start_index is not None:
            results, start_index = self.get_list(start_index)
            for obj in results:
                yield obj


ApiResponse = namedtuple('ApiResponse', 'results next_index')
