from datetime import datetime

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from fakecouch import FakeCouchDb
from kafka import KafkaConsumer
from unittest.mock import patch

from pillowtop.dao.exceptions import DocumentMismatchError
from pillowtop.feed.interface import Change, ChangeMeta

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    change_meta_from_kafka_message,
)
from corehq.apps.change_feed.data_sources import SOURCE_COUCH
from corehq.apps.change_feed.pillow import get_change_feed_pillow_for_db
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.pillows.case import get_case_pillow
from corehq.apps.es.cases import case_adapter
from corehq.util.elastic import ensure_index_deleted


class ChangeFeedPillowTest(SimpleTestCase):
    # note: these tests require a valid kafka setup running

    def setUp(self):
        super(ChangeFeedPillowTest, self).setUp()
        self._fake_couch = FakeCouchDb()
        # use a 'real' db name here so that we don't cause other
        # tests down the line to fail.
        # Specifically KafkaChangeFeedTest.test_multiple_topics_with_partial_checkpoint
        self._fake_couch.dbname = 'test_commcarehq'
        self.consumer = KafkaConsumer(
            topics.CASE_SQL,
            bootstrap_servers=settings.KAFKA_BROKERS,
            consumer_timeout_ms=100,
            enable_auto_commit=False,
        )
        try:
            # This initialized the consumer listening from the latest offset
            next(self.consumer)
        except StopIteration:
            pass
        self.pillow = get_change_feed_pillow_for_db('fake-changefeed-pillow-id', self._fake_couch)

    def tearDown(self):
        self.consumer.close()
        super(ChangeFeedPillowTest, self).tearDown()

    def test_process_change(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'kafka-test-domain',
        }
        self.pillow.process_change(Change(id='test-id', sequence_id='3', document=document))

        message = next(self.consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(SOURCE_COUCH, change_meta.data_source_type)
        self.assertEqual(self._fake_couch.dbname, change_meta.data_source_name)
        self.assertEqual('test-id', change_meta.document_id)
        self.assertEqual(document['doc_type'], change_meta.document_type)
        self.assertEqual(document['type'], change_meta.document_subtype)
        self.assertEqual(document['domain'], change_meta.domain)
        self.assertEqual(False, change_meta.is_deletion)

        with self.assertRaises(StopIteration):
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
            self.pillow = get_case_pillow(skip_ucr=True)

    def tearDown(self):
        ensure_index_deleted(case_adapter.index_name)

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
            '_id': 'a_cool_identifier',
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


class TestKafkaProcessor(TestCase):

    def setUp(self):
        self._fake_couch = FakeCouchDb()
        self._fake_couch.dbname = 'test_commcarehq'
        self.pillow = get_change_feed_pillow_for_db('fake-changefeed-pillow-id', self._fake_couch)

    def test_deleted_couch_doc(self):
        doc = {
            '_id': '980023a6852643a19b87f2142b0c3ce1',
            '_rev': 'v3-980023a6852643a19b87f2142b0c3ce1',
            'doc_type': 'Group-Deleted',
            'domain': 'test',
        }
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(doc_id=doc["_id"])

        change = Change(doc["_id"], "24066c14d2154fbfb3b89407075809aa", doc)
        self.pillow.process_change(change)
        DeletedCouchDoc.objects.get(doc_id=doc["_id"])  # should not raise
