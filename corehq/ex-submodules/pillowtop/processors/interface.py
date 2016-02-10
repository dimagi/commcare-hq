from abc import ABCMeta, abstractmethod


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change, do_set_checkpoint):
        pass
