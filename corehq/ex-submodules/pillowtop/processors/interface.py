from abc import ABCMeta, abstractmethod


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change):
        pass

    def checkpoint_updated(self):
        pass
