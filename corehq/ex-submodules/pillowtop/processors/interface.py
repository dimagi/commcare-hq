from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta

from pillowtop.const import CHECKPOINT_FREQUENCY
from pillowtop.pillow.interface import CheckpointEventListener

PYTHONPILLOW_CHUNK_SIZE = 250
PYTHONPILLOW_CHECKPOINT_FREQUENCY = CHECKPOINT_FREQUENCY * 10
PYTHONPILLOW_MAX_WAIT_TIME = 60


class PillowProcessor(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def process_change(self, pillow_instance, change, is_retry_attempt=False):
        pass


class ChunkedPillowProcessor(PillowProcessor):
    def __init__(self, chunk_size=PYTHONPILLOW_CHUNK_SIZE):
        self.change_queue = []
        # explicitly check against None since we want to pass chunk_size=0 through
        self.chunk_size = chunk_size if chunk_size is not None else PYTHONPILLOW_CHUNK_SIZE
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
        return wait_time > timedelta(seconds=PYTHONPILLOW_MAX_WAIT_TIME)

    @abstractmethod
    def process_individual_change(self, change):
        pass


class ChunkedProcessorCheckpointListener(CheckpointEventListener):
    def __init__(self, chunked_processor):
        self.processor = chunked_processor

    def checkpoint_updated(self, updated_to):
        if self.processor.use_chunking:
            self.processor.process_chunk()
