from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta

MAX_WAIT_TIME = 60


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change, is_retry_attempt=False):
        pass
