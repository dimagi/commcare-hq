# coding=utf-8
from django.conf import settings
from django.test import SimpleTestCase
from fakecouch import FakeCouchDb
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout, KafkaUnavailableError
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.pillow import get_change_feed_pillow_for_db
from corehq.apps.change_feed.data_sources import COUCH
from corehq.util.test_utils import trap_extra_setup
from pillowtop.feed.interface import Change


class ChangeFeedPillowTest(SimpleTestCase):
    # note: these tests require a valid kafka setup running

    def setUp(self):
        self._fake_couch = FakeCouchDb()
        self._fake_couch.dbname = 'test-couchdb'
        with trap_extra_setup(KafkaUnavailableError):
            self.consumer = KafkaConsumer(
                topics.CASE,
                group_id='test-consumer',
                bootstrap_servers=[settings.KAFKA_URL],
                consumer_timeout_ms=100,
            )
        self.pillow = get_change_feed_pillow_for_db('fake-changefeed-pillow-id', self._fake_couch)

    def test_process_change(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'kafka-test-domain',
        }
        self.pillow.processor(Change(id='test-id', sequence_id='3', document=document))
        message = self.consumer.next()

        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(COUCH, change_meta.data_source_type)
        self.assertEqual(self._fake_couch.dbname, change_meta.data_source_name)
        self.assertEqual('test-id', change_meta.document_id)
        self.assertEqual(document['doc_type'], change_meta.document_type)
        self.assertEqual(document['type'], change_meta.document_subtype)
        self.assertEqual(document['domain'], change_meta.domain)
        self.assertEqual(False, change_meta.is_deletion)

        with self.assertRaises(ConsumerTimeout):
            self.consumer.next()

    def test_process_change_with_unicode_domain(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': u'हिंदी',
        }
        self.pillow.processor(Change(id='test-id', sequence_id='3', document=document))
        message = self.consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(document['domain'], change_meta.domain)

    def test_no_domain(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': None,
        }
        self.pillow.processor(Change(id='test-id', sequence_id='3', document=document))
        message = self.consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(document['domain'], change_meta.domain)
