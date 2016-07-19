from abc import ABCMeta, abstractmethod

MAX_WAIT_TIME = 60


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change):
        pass
