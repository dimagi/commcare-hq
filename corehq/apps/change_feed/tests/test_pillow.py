from django.conf import settings
from django.test import SimpleTestCase
from fakecouch import FakeCouchDb
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_client
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.pillow import ChangeFeedPillow
from corehq.apps.change_feed.data_sources import COUCH
from pillowtop.feed.interface import Change


class ChangeFeedPillowTest(SimpleTestCase):
    # note: these tests require a valid kafka setup running

    def setUp(cls):
        cls._fake_couch = FakeCouchDb()
        cls._fake_couch.dbname = 'test-couchdb'

    def test_process_change(self):
        consumer = KafkaConsumer(
            topics.CASE,
            group_id='test-consumer',
            bootstrap_servers=[settings.KAFKA_URL],
            consumer_timeout_ms=100,
        )
        pillow = ChangeFeedPillow(self._fake_couch, kafka=get_kafka_client(), checkpoint=None)
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'kafka-test-domain',
        }
        pillow.process_change(Change(id='test-id', sequence_id='3', document=document))
        message = consumer.next()

        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(COUCH, change_meta.data_source_type)
        self.assertEqual(self._fake_couch.dbname, change_meta.data_source_name)
        self.assertEqual('test-id', change_meta.document_id)
        self.assertEqual(document['doc_type'], change_meta.document_type)
        self.assertEqual(document['type'], change_meta.document_subtype)
        self.assertEqual(document['domain'], change_meta.domain)
        self.assertEqual(False, change_meta.is_deletion)

        with self.assertRaises(ConsumerTimeout):
            consumer.next()
