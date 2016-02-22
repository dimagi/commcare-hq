import uuid
from django.test import SimpleTestCase
from kafka import KeyedProducer
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.producer import send_to_kafka
from dimagi.utils.decorators.memoized import memoized
from pillowtop.feed.interface import ChangeMeta


class KafkaChangeFeedTest(SimpleTestCase):

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


@memoized
def _get_producer():
    return KeyedProducer(get_kafka_client_or_none())


def publish_stub_change(topic):
    meta = ChangeMeta(document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name')
    send_to_kafka(_get_producer(), topic, meta)
    return meta
