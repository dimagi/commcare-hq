from __future__ import absolute_import
from abc import ABCMeta, abstractmethod
import six


class PillowProcessor(six.with_metaclass(ABCMeta, object)):
    @abstractmethod
    def process_change(self, pillow_instance, change):
        pass

    def checkpoint_updated(self):
        pass
