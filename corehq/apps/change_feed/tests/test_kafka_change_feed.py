from django.test import SimpleTestCase
from kafka import KeyedProducer
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.producer import send_to_kafka
from pillowtop.feed.interface import ChangeMeta


class KafkaChangeFeedTest(SimpleTestCase):

    def test_multiple_topics(self):
        feed = KafkaChangeFeed(topics=[topics.FORM, topics.CASE], group_id='test-kafka-feed')
        self.assertEqual(0, len(list(feed.iter_changes(since=None, forever=False))))
        producer = KeyedProducer(get_kafka_client_or_none())
        offsets = feed.get_current_offsets()
        send_to_kafka(producer, topics.FORM,
                      ChangeMeta(document_id='1', data_source_type='form', data_source_name='form'))
        send_to_kafka(producer, topics.CASE,
                      ChangeMeta(document_id='2', data_source_type='case', data_source_name='case'))
        send_to_kafka(producer, topics.FORM_SQL,
                      ChangeMeta(document_id='3', data_source_type='form-sql', data_source_name='form-sql'))
        send_to_kafka(producer, topics.CASE_SQL,
                      ChangeMeta(document_id='4', data_source_type='case-sql', data_source_name='case-sql'))

        changes = list(feed.iter_changes(since=offsets, forever=False))
        self.assertEqual(2, len(changes))
        self.assertEqual(set(['1', '2']), set([change.id for change in changes]))
