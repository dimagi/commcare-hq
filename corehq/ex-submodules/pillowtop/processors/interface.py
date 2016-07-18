from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta

from pillowtop.pillow.interface import CheckpointEventListener

MAX_WAIT_TIME = 60


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change, is_retry_attempt=False):
        pass


class ChunkedPillowProcessor(PillowProcessor):
    def __init__(self, chunk_size=250):
        self.change_queue = []
        self.chunk_size = chunk_size
        self.use_chunking = chunk_size > 0
        self.last_processed_time = None

    def process_change(self, pillow_instance, change, is_retry_attempt=False):
        if self.use_chunking and not is_retry_attempt:
            self.change_queue.append(change)
            if self.queue_full or self.wait_expired:
                self.process_chunk()
        else:
            self.process_individual_change(change)

    def process_chunk(self):
        for change in self.change_queue:
            self.process_individual_change(change)

        # reset the queue after we've processed this chunk
        self.change_queue = []
        self.last_processed_time = datetime.utcnow()

    @property
    def queue_full(self):
        return len(self.change_queue) > self.chunk_size

    @property
    def wait_expired(self):
        if not self.last_processed_time:
            return False

        wait_time = datetime.utcnow() - self.last_processed_time
        return wait_time > timedelta(seconds=MAX_WAIT_TIME)

    @abstractmethod
    def process_individual_change(self, change):
        pass


class ChunkedProcessorCheckpointListener(CheckpointEventListener):
    def __init__(self, chunked_processor):
        self.processor = chunked_processor

    def checkpoint_updated(self, updated_to):
        if self.processor.use_chunking:
            self.processor.process_chunk()
