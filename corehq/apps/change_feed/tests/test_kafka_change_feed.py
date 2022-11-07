import uuid
from copy import deepcopy

from django.test import SimpleTestCase, TestCase

from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
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
            next(feed.iter_changes(since=since, forever=False))

    def test_non_expired_checkpoint_iteration_strict(self):
        feed = KafkaChangeFeed(topics=[topics.FORM_SQL, topics.CASE_SQL], client_id='test-kafka-feed', strict=True)
        first_available_offsets = get_multi_topic_first_available_offsets([topics.FORM_SQL, topics.CASE_SQL])
        next(feed.iter_changes(since=first_available_offsets, forever=False))


class KafkaCheckpointTest(TestCase):

    def test_checkpoint_with_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM_SQL, topics.CASE_SQL], client_id='test-kafka-feed')
        pillow_name = 'test-multi-topic-checkpoints'
        checkpoint = KafkaPillowCheckpoint(pillow_name, feed.topics)
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

    def test_dont_create_checkpoint_past_current(self):
        pillow_name = 'test-checkpoint-reset'

        # initialize change feed and pillow
        feed = KafkaChangeFeed(topics=topics.USER_TOPICS, client_id='test-kafka-feed')
        checkpoint = KafkaPillowCheckpoint(pillow_name, feed.topics)
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
        self.assertEqual(
            pillow.get_last_checkpoint_sequence(), {(topics.COMMCARE_USER, 0): 0, (topics.WEB_USER, 0): 0}
        )

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
