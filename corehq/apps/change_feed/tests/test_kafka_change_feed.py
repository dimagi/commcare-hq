import uuid
from copy import deepcopy

from django.test import SimpleTestCase, TestCase

from kafka.future import Future
from mock import Mock

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
from corehq.apps.change_feed.producer import (
    CHANGE_ERROR,
    CHANGE_PRE_SEND,
    CHANGE_SENT,
    KAFKA_AUDIT_LOGGER,
    ChangeProducer,
    producer,
)
from corehq.apps.change_feed.topics import (
    get_multi_topic_first_available_offsets,
)
from corehq.util.test_utils import capture_log_output


class KafkaChangeFeedTest(SimpleTestCase):

    def test_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM, topics.CASE], client_id='test-kafka-feed')
        self.assertEqual(0, len(list(feed.iter_changes(since=None, forever=False))))
        offsets = feed.get_latest_offsets()
        expected_metas = [publish_stub_change(topics.FORM), publish_stub_change(topics.CASE)]
        unexpected_metas = [publish_stub_change(topics.FORM_SQL), publish_stub_change(topics.CASE_SQL)]
        changes = list(feed.iter_changes(since=offsets, forever=False))
        self.assertEqual(2, len(changes))
        found_change_ids = set([change.id for change in changes])
        self.assertEqual(set([meta.document_id for meta in expected_metas]), found_change_ids)
        for unexpected in unexpected_metas:
            self.assertTrue(unexpected.document_id not in found_change_ids)

    def test_expired_checkpoint_iteration_strict(self):
        feed = KafkaChangeFeed(topics=[topics.FORM, topics.CASE], client_id='test-kafka-feed', strict=True)
        first_available_offsets = get_multi_topic_first_available_offsets([topics.FORM, topics.CASE])
        since = {
            topic_partition: offset - 1
            for topic_partition, offset in first_available_offsets.items()
        }
        with self.assertRaises(UnavailableKafkaOffset):
            next(feed.iter_changes(since=since, forever=False))

    def test_non_expired_checkpoint_iteration_strict(self):
        feed = KafkaChangeFeed(topics=[topics.FORM, topics.CASE], client_id='test-kafka-feed', strict=True)
        first_available_offsets = get_multi_topic_first_available_offsets([topics.FORM, topics.CASE])
        next(feed.iter_changes(since=first_available_offsets, forever=False))


class KafkaCheckpointTest(TestCase):

    def test_checkpoint_with_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM, topics.CASE], client_id='test-kafka-feed')
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
        self.assertEqual(set([(topics.FORM, 0), (topics.CASE, 0)]), set(offsets.keys()))

        # send a few changes to kafka so they should be picked up by the pillow
        publish_stub_change(topics.FORM)
        publish_stub_change(topics.FORM)
        publish_stub_change(topics.CASE)
        publish_stub_change(topics.CASE)
        publish_stub_change(topics.CASE_SQL)
        pillow.process_changes(since=offsets, forever=False)
        self.assertEqual(4, processor.count)
        self.assertEqual(feed.get_current_checkpoint_offsets(), pillow.get_last_checkpoint_sequence())
        publish_stub_change(topics.FORM)
        publish_stub_change(topics.FORM)
        publish_stub_change(topics.CASE)
        publish_stub_change(topics.CASE)
        publish_stub_change(topics.CASE_SQL)
        pillow.process_changes(pillow.get_last_checkpoint_sequence(), forever=False)
        self.assertEqual(8, processor.count)
        self.assertEqual(feed.get_current_checkpoint_offsets(), pillow.get_last_checkpoint_sequence())

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


def publish_stub_change(topic, kafka_producer=None):
    meta = ChangeMeta(document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name')
    (kafka_producer or producer).send_change(topic, meta)
    return meta


class TestKafkaAuditLogging(SimpleTestCase):
    def test_success_synchronous(self):
        self._test_success(auto_flush=True)

    def test_success_asynchronous(self):
        self._test_success(auto_flush=False)

    def test_error_synchronous(self):
        kafka_producer = ChangeProducer()
        future = Future()
        future.get = Mock(side_effect=Exception())
        kafka_producer.producer.send = Mock(return_value=future)

        meta = ChangeMeta(
            document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name'
        )

        with capture_log_output(KAFKA_AUDIT_LOGGER) as logs:
            with self.assertRaises(Exception):
                kafka_producer.send_change(topics.CASE, meta)

        self._check_logs(logs, meta.document_id, [CHANGE_PRE_SEND, CHANGE_ERROR])

    def test_error_asynchronous(self):
        kafka_producer = ChangeProducer(auto_flush=False)
        future = Future()
        kafka_producer.producer.send = Mock(return_value=future)

        meta = ChangeMeta(
            document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name'
        )

        with capture_log_output(KAFKA_AUDIT_LOGGER) as logs:
            kafka_producer.send_change(topics.CASE, meta)
            future.failure(Exception())

        self._check_logs(logs, meta.document_id, [CHANGE_PRE_SEND, CHANGE_ERROR])

    def _test_success(self, auto_flush):
        kafka_producer = ChangeProducer(auto_flush=auto_flush)
        with capture_log_output(KAFKA_AUDIT_LOGGER) as logs:
            meta = publish_stub_change(topics.CASE, kafka_producer)
            if not auto_flush:
                kafka_producer.flush()
        self._check_logs(logs, meta.document_id, [CHANGE_PRE_SEND, CHANGE_SENT])

    def _check_logs(self, captured_logs, doc_id, events):
        lines = captured_logs.get_output().splitlines()
        self.assertEqual(len(events), len(lines))
        for event, line in zip(events, lines):
            self.assertIn(doc_id, line)
            self.assertIn(event, line)
