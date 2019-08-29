import abc


class AbstractRateCounter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get(self, scope):
        raise NotImplementedError()

    @abc.abstractmethod
    def increment(self, scope, delta):
        raise NotImplementedError()

    @abc.abstractmethod
    def increment_and_get(self, scope, delta):
        raise NotImplementedError()
