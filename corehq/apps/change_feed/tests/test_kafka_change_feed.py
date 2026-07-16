import uuid
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from django.test import SimpleTestCase, TestCase
from kafka import TopicPartition

from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.feed.interface import ChangeMeta
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.sample import CountingProcessor

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.change_feed.exceptions import UnavailableKafkaOffset
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed.topics import (
    get_multi_topic_first_available_offsets,
)


class KafkaChangeFeedTest(SimpleTestCase):

    def test_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM_SQL, topics.CASE_SQL], client_id='test-kafka-feed')
        self.assertEqual(0, len(list(feed.iter_changes(since=None, forever=False))))
        offsets = feed.get_latest_offsets()
        expected_metas = [publish_stub_change(topics.FORM_SQL), publish_stub_change(topics.CASE_SQL)]
        unexpected_metas = [publish_stub_change(topics.COMMCARE_USER), publish_stub_change(topics.WEB_USER)]
        changes = list(feed.iter_changes(since=offsets, forever=False))
        self.assertEqual(2, len(changes))
        found_change_ids = set([change.id for change in changes])
        self.assertEqual(set([meta.document_id for meta in expected_metas]), found_change_ids)
        for unexpected in unexpected_metas:
            self.assertTrue(unexpected.document_id not in found_change_ids)

    def test_expired_checkpoint_iteration_strict(self):
        feed = KafkaChangeFeed(topics=[topics.FORM_SQL, topics.CASE_SQL], client_id='test-kafka-feed', strict=True)
        first_available_offsets = get_multi_topic_first_available_offsets([topics.FORM_SQL, topics.CASE_SQL])
        since = {
            topic_partition: offset - 1
            for topic_partition, offset in first_available_offsets.items()
        }
        with self.assertRaises(UnavailableKafkaOffset):
            next(feed.iter_changes(since=since, forever=False), None)

    def test_non_expired_checkpoint_iteration_strict(self):
        feed = KafkaChangeFeed(topics=[topics.FORM_SQL, topics.CASE_SQL], client_id='test-kafka-feed', strict=True)
        first_available_offsets = get_multi_topic_first_available_offsets([topics.FORM_SQL, topics.CASE_SQL])
        # should not raise UnavailableKafkaOffset
        next(feed.iter_changes(since=first_available_offsets, forever=False), None)

    def test_filter_partitions_without_migration_process(self):
        feed = KafkaChangeFeed(
            topics=[topics.CASE_SQL],
            client_id='test-kafka-feed',
            num_processes=3,
            process_num=0,
            dedicated_migration_process=False,
        )
        partitions = [0, 1, 2, 3, 4, 5]
        result = feed._filter_partitions(partitions)
        assert result == [0, 3], result

    def test_filter_partitions_for_migration_process(self):
        feed = KafkaChangeFeed(
            topics=[topics.CASE_SQL],
            client_id='test-kafka-feed',
            num_processes=3,
            process_num=0,
            dedicated_migration_process=True,
        )
        partitions = [0, 1, 2, 3, 4, 5]
        result = feed._filter_partitions(partitions)
        assert result is None, result

    def test_filter_partitions_for_non_migration_process(self):
        feed = KafkaChangeFeed(
            topics=[topics.CASE_SQL],
            client_id='test-kafka-feed',
            num_processes=3,
            process_num=2,
            dedicated_migration_process=True,
        )
        partitions = [0, 1, 2, 3, 4, 5]
        result = feed._filter_partitions(partitions)
        assert result == [1, 3, 5], result

    def test_iter_changes_forever(self):
        class TimeoutConsumer:
            values = iter(range(1, 10))

            def __iter__(self):
                for value in self.values:
                    yield Msg(value)
                    if value > 4:
                        raise StopConsuming
                    if value % 2 == 0:
                        return  # stop iteration -> simulate timeout

        feed = KafkaChangeFeed(topics=None, client_id='test', strict=True)
        changes = []
        with (
            patch.object(feed, '_init_consumer'),
            patch.object(feed, '_consumer', TimeoutConsumer()),
            patch("corehq.apps.change_feed.consumer.feed.change_from_kafka_message", lambda msg: msg.value),
            pytest.raises(StopConsuming),
        ):
            for change in feed.iter_changes(since=None, forever=True):
                changes.append(change)

        # expect None (timeout) after the consumer completes each iteration
        assert changes == [1, 2, None, 3, 4, None, 5], changes


class Msg:
    def __init__(self, value):
        self.value = value
        self.topic = 'test'
        self.partition = 0
        self.offset = 0


class StopConsuming(Exception):
    pass


class KafkaCheckpointTest(TestCase):

    def test_checkpoint_with_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM_SQL, topics.CASE_SQL], client_id='test-kafka-feed')
        pillow_name = 'test-multi-topic-checkpoints'
        checkpoint = PillowCheckpoint(pillow_name, feed.sequence_format)
        processor = CountingProcessor()
        pillow = ConstructedPillow(
            name=pillow_name,
            checkpoint=checkpoint,
            change_feed=feed,
            processor=processor,
            change_processed_event_handler=KafkaCheckpointEventHandler(
                checkpoint=checkpoint, checkpoint_frequency=1, change_feed=feed
            )
        )
        offsets = feed.get_latest_offsets()
        self.assertEqual(set([(topics.FORM_SQL, 0), (topics.CASE_SQL, 0)]), set(offsets.keys()))

        # send a few changes to kafka so they should be picked up by the pillow
        publish_stub_change(topics.FORM_SQL)
        publish_stub_change(topics.FORM_SQL)
        publish_stub_change(topics.CASE_SQL)
        publish_stub_change(topics.CASE_SQL)
        publish_stub_change(topics.COMMCARE_USER)
        pillow.process_changes(since=offsets, forever=False)
        self.assertEqual(4, processor.count)
        self.assertEqual(feed.get_current_checkpoint_offsets(), pillow.get_last_checkpoint_sequence())
        publish_stub_change(topics.FORM_SQL)
        publish_stub_change(topics.FORM_SQL)
        publish_stub_change(topics.CASE_SQL)
        publish_stub_change(topics.CASE_SQL)
        publish_stub_change(topics.COMMCARE_USER)
        pillow.process_changes(pillow.get_last_checkpoint_sequence(), forever=False)
        self.assertEqual(8, processor.count)
        self.assertEqual(feed.get_current_checkpoint_offsets(), pillow.get_last_checkpoint_sequence())

    def test_idle_does_not_recommit_when_caught_up(self):
        # Guards the real-object comparison in update_checkpoint_on_idle: the
        # consumed offsets (TopicPartition-keyed) must compare equal to the
        # committed offsets (tuple-keyed) once caught up, so an idle tick is a
        # no-op rather than a redundant write every timeout.
        feed = KafkaChangeFeed(topics=[topics.FORM_SQL], client_id='test-kafka-feed')
        pillow_name = 'test-idle-no-recommit'
        checkpoint = PillowCheckpoint(pillow_name, feed.sequence_format)
        handler = KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=1, change_feed=feed,
        )
        pillow = ConstructedPillow(
            name=pillow_name,
            checkpoint=checkpoint,
            change_feed=feed,
            processor=CountingProcessor(),
            change_processed_event_handler=handler,
        )
        offsets = feed.get_latest_offsets()
        publish_stub_change(topics.FORM_SQL)
        pillow.process_changes(since=offsets, forever=False)

        # checkpoint is now caught up to the consumed position
        self.assertEqual(feed.get_current_checkpoint_offsets(), pillow.get_last_checkpoint_sequence())
        # ...so an idle tick must not write the checkpoint again
        self.assertFalse(handler.update_checkpoint_on_idle())

    def test_dont_create_checkpoint_past_current(self):
        pillow_name = 'test-checkpoint-reset'

        # initialize change feed and pillow
        feed = KafkaChangeFeed(topics=topics.USER_TOPICS, client_id='test-kafka-feed')
        checkpoint = PillowCheckpoint(pillow_name, feed.sequence_format)
        processor = CountingProcessor()
        pillow = ConstructedPillow(
            name=pillow_name,
            checkpoint=checkpoint,
            change_feed=feed,
            processor=processor,
            change_processed_event_handler=KafkaCheckpointEventHandler(
                checkpoint=checkpoint, checkpoint_frequency=1, change_feed=feed
            )
        )

        original_kafka_offsets = feed.get_latest_offsets()
        current_kafka_offsets = deepcopy(original_kafka_offsets)
        self.assertEqual(feed.get_current_checkpoint_offsets(), {})
        self.assertEqual(pillow.get_last_checkpoint_sequence(), {})

        publish_stub_change(topics.COMMCARE_USER)
        # the following line causes tests to fail if you have multiple partitions
        current_kafka_offsets[(topics.COMMCARE_USER, 0)] += 1
        pillow.process_changes(since=original_kafka_offsets, forever=False)
        self.assertEqual(1, processor.count)
        self.assertEqual(feed.get_current_checkpoint_offsets(), current_kafka_offsets)


def publish_stub_change(topic):
    meta = ChangeMeta(document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name')
    producer.send_change(topic, meta)
    return meta


class KafkaCheckpointEventHandlerIdleTest(SimpleTestCase):
    """When the consumer catches up and is idle, the checkpoint should be
    updated to the consumed offset to accurately reflect its state."""

    def _make_handler(self, consumed_offsets, committed_offsets):
        change_feed = Mock(spec=KafkaChangeFeed)
        change_feed.get_current_checkpoint_offsets.return_value = consumed_offsets
        checkpoint = Mock()
        checkpoint.get_or_create_wrapped.return_value.wrapped_sequence = committed_offsets
        handler = KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=10, change_feed=change_feed,
        )
        return handler, checkpoint

    def test_update_when_consumed_offset_is_ahead(self):
        tp = TopicPartition('group', 0)
        handler, checkpoint = self._make_handler(
            consumed_offsets={tp: 5}, committed_offsets={tp: 3},
        )
        assert handler.update_checkpoint_on_idle() is True
        checkpoint.update_to.assert_called_once_with({tp: 5})

    def test_no_update_when_already_caught_up(self):
        tp = TopicPartition('group', 0)
        handler, checkpoint = self._make_handler(
            consumed_offsets={tp: 5}, committed_offsets={tp: 5},
        )
        assert handler.update_checkpoint_on_idle() is False
        checkpoint.update_to.assert_not_called()

    def test_ignores_partitions_owned_by_other_processes(self):
        tp = TopicPartition('group', 0)
        handler, checkpoint = self._make_handler(
            consumed_offsets={tp: 5}, committed_offsets={tp: 5, ('group', 1): 2},
        )
        assert handler.update_checkpoint_on_idle() is False
        checkpoint.update_to.assert_not_called()

    def test_updates_own_partition_even_when_another_process_appears_caught_up(self):
        tp = TopicPartition('group', 0)
        handler, checkpoint = self._make_handler(
            consumed_offsets={tp: 5}, committed_offsets={tp: 3, ('group', 1): 5},
        )
        assert handler.update_checkpoint_on_idle() is True
        checkpoint.update_to.assert_called_once_with({tp: 5})
