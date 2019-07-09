import abc

import six


class AbstractRateCounter(six.with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def get(self, scope):
        raise NotImplementedError()

    @abc.abstractmethod
    def increment(self, scope, delta):
        raise NotImplementedError()

    @abc.abstractmethod
    def increment_and_get(self, scope, delta):
        raise NotImplementedError()
