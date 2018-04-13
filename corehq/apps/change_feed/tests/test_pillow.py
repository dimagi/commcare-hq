# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from mock import patch
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from fakecouch import FakeCouchDb
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout, KafkaUnavailableError
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.pillow import get_change_feed_pillow_for_db
from corehq.apps.change_feed.data_sources import COUCH
from corehq.pillows.case import get_case_to_elasticsearch_pillow
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.util.test_utils import trap_extra_setup
from corehq.util.elastic import ensure_index_deleted
from pillowtop.feed.interface import Change, ChangeMeta
from pillowtop.dao.exceptions import DocumentMismatchError


class ChangeFeedPillowTest(SimpleTestCase):
    # note: these tests require a valid kafka setup running

    def setUp(self):
        self._fake_couch = FakeCouchDb()
        # use a 'real' db name here so that we don't cause other
        # tests down the line to fail.
        # Specifically KafkaChangeFeedTest.test_multiple_topics_with_partial_checkpoint
        self._fake_couch.dbname = 'test_commcarehq'
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
        self.pillow.process_change(Change(id='test-id', sequence_id='3', document=document))
        message = next(self.consumer)

        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(COUCH, change_meta.data_source_type)
        self.assertEqual(self._fake_couch.dbname, change_meta.data_source_name)
        self.assertEqual('test-id', change_meta.document_id)
        self.assertEqual(document['doc_type'], change_meta.document_type)
        self.assertEqual(document['type'], change_meta.document_subtype)
        self.assertEqual(document['domain'], change_meta.domain)
        self.assertEqual(False, change_meta.is_deletion)

        with self.assertRaises(ConsumerTimeout):
            next(self.consumer)

    def test_process_change_with_unicode_domain(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'हिंदी',
        }
        self.pillow.process_change(Change(id='test-id', sequence_id='3', document=document))
        message = next(self.consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(document['domain'], change_meta.domain)

    def test_no_domain(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': None,
        }
        self.pillow.process_change(Change(id='test-id', sequence_id='3', document=document))
        message = next(self.consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(document['domain'], change_meta.domain)

    def test_publish_timestamp(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': None,
        }
        self.pillow.process_change(Change(id='test-id', sequence_id='3', document=document))
        message = next(self.consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertLessEqual(change_meta.publish_timestamp, datetime.utcnow())


class TestElasticProcessorPillows(TestCase):

    def setUp(self):
        with patch('pillowtop.checkpoints.manager.get_or_create_checkpoint'):
            self.pillow = get_case_to_elasticsearch_pillow()

    def tearDown(self):
        ensure_index_deleted(CASE_INDEX_INFO.index)

    def test_mismatched_rev(self):
        """
        Ensures that if the rev from kafka does not match the rev fetched from the document,
        then we throw an error
        """
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'rev-domain',
            '_rev': '3-me',
        }
        broken_metadata = ChangeMeta(
            document_id='test-id',
            document_rev='mismatched',
            data_source_type='couch',
            data_source_name='test_commcarehq'
        )
        good_metadata = ChangeMeta(
            document_id='test-id',
            document_rev='3-me',
            data_source_type='couch',
            data_source_name='test_commcarehq'
        )
        newer_metadata = ChangeMeta(
            document_id='test-id',
            # Rev is lower than the rev in the fetched document and we should not throw an error
            document_rev='2-me',
            data_source_type='couch',
            data_source_name='test_commcarehq'
        )
        stale_metadata = ChangeMeta(
            document_id='test-id',
            document_rev='4-me',  # Rev is higher than the rev in the fetched document so it is stale
            data_source_type='couch',
            data_source_name='test_commcarehq'
        )

        with self.assertRaises(DocumentMismatchError):
            self.pillow.process_change(
                Change(
                    id='test-id',
                    sequence_id='3',
                    document=document,
                    metadata=broken_metadata
                )
            )

        with self.assertRaises(DocumentMismatchError):
            self.pillow.process_change(
                Change(
                    id='test-id',
                    sequence_id='3',
                    document=document,
                    metadata=stale_metadata
                )
            )

        try:
            self.pillow.process_change(
                Change(
                    id='test-id',
                    sequence_id='3',
                    document=document,
                    metadata=good_metadata
                )
            )
        except DocumentMismatchError:
            self.fail('Incorectly raise a DocumentMismatchError for matching revs')

        try:
            self.pillow.process_change(
                Change(
                    id='test-id',
                    sequence_id='3',
                    document=document,
                    metadata=newer_metadata
                )
            )
        except DocumentMismatchError:
            self.fail('Incorectly raise a DocumentMismatchError for matching revs')
