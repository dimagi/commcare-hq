import uuid

from django.test import TestCase
from kafka.common import KafkaUnavailableError
from unittest.mock import MagicMock

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed.producer import producer
from corehq.util.test_utils import trap_extra_setup
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.feed.interface import ChangeMeta
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.sample import ChunkedCountProcessor


class ChunkedProcessingTest(TestCase):

    def _produce_changes(self, count):
        for i in range(count):
            meta = ChangeMeta(
                document_id=uuid.uuid4().hex,
                data_source_type='dummy-type',
                data_source_name='dummy-name',
            )
            producer.send_change(topics.CASE_SQL, meta)

    @trap_extra_setup(KafkaUnavailableError)
    def test_basic(self):
        # setup
        feed = KafkaChangeFeed(topics=[topics.CASE_SQL], client_id='test-kafka-feed')
        pillow_name = 'test-chunked-processing'
        checkpoint = PillowCheckpoint(pillow_name, feed.sequence_format)
        processor = ChunkedCountProcessor()
        original_process_change = processor.process_change
        original_process_changes_chunk = processor.process_changes_chunk

        pillow = ConstructedPillow(
            name=pillow_name,
            checkpoint=checkpoint,
            change_feed=feed,
            processor=processor,
            change_processed_event_handler=KafkaCheckpointEventHandler(
                checkpoint=checkpoint, checkpoint_frequency=1, change_feed=feed
            ),
            processor_chunk_size=2
        )

        since = feed.get_latest_offsets()
        self._produce_changes(2)
        # pillow should use process_changes_chunk (make process_change raise an exception for test)
        processor.process_change = MagicMock(side_effect=Exception('_'))
        pillow.process_changes(since=since, forever=False)
        self.assertEqual(processor.count, 2)

        self._produce_changes(2)
        # if process_changes_chunk raises exception, pillow should use process_change
        processor.process_change = original_process_change
        processor.process_changes_chunk = MagicMock(side_effect=Exception('_'))
        pillow.process_changes(since=pillow.get_last_checkpoint_sequence(), forever=False)
        self.assertEqual(processor.count, 4)

        self._produce_changes(1)
        # offsets after full chunk should still be processed
        processor.process_change = MagicMock(side_effect=Exception('_'))
        processor.process_changes_chunk = original_process_changes_chunk
        pillow.process_changes(since=pillow.get_last_checkpoint_sequence(), forever=False)
        self.assertEqual(processor.count, 5)
