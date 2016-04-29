import uuid
from django.test import SimpleTestCase, TestCase
from kafka import KeyedProducer
from kafka.common import KafkaUnavailableError
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.apps.change_feed.producer import send_to_kafka
from corehq.util.test_utils import trap_extra_setup
from dimagi.utils.decorators.memoized import memoized
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.feed.interface import ChangeMeta
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.sample import CountingProcessor


class KafkaChangeFeedTest(SimpleTestCase):

    @trap_extra_setup(KafkaUnavailableError)
    def test_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM, topics.CASE], group_id='test-kafka-feed')
        self.assertEqual(0, len(list(feed.iter_changes(since=None, forever=False))))
        offsets = feed.get_current_offsets()
        expected_metas = [publish_stub_change(topics.FORM), publish_stub_change(topics.CASE)]
        unexpected_metas = [publish_stub_change(topics.FORM_SQL), publish_stub_change(topics.CASE_SQL)]
        changes = list(feed.iter_changes(since=offsets, forever=False))
        self.assertEqual(2, len(changes))
        found_change_ids = set([change.id for change in changes])
        self.assertEqual(set([meta.document_id for meta in expected_metas]), found_change_ids)
        for unexpected in unexpected_metas:
            self.assertTrue(unexpected.document_id not in found_change_ids)


class KafkaCheckpointTest(TestCase):

    @trap_extra_setup(KafkaUnavailableError)
    def test_checkpoint_with_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM, topics.CASE], group_id='test-kafka-feed')
        pillow_name = 'test-multi-topic-checkpoints'
        checkpoint = PillowCheckpoint(pillow_name)
        processor = CountingProcessor()
        pillow = ConstructedPillow(
            name=pillow_name,
            checkpoint=checkpoint,
            change_feed=feed,
            processor=processor,
            change_processed_event_handler=MultiTopicCheckpointEventHandler(
                checkpoint=checkpoint, checkpoint_frequency=1, change_feed=feed
            )
        )
        offsets = feed.get_current_offsets()
        self.assertEqual(set([topics.FORM, topics.CASE]), set(offsets.keys()))

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


@memoized
def _get_producer():
    return KeyedProducer(get_kafka_client_or_none())


def publish_stub_change(topic):
    meta = ChangeMeta(document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name')
    send_to_kafka(_get_producer(), topic, meta)
    return meta
