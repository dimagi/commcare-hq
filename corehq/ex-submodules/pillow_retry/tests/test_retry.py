from django.conf import settings
from django.test import TestCase
from fakecouch import FakeCouchDb
from kafka import KafkaConsumer
from unittest.mock import MagicMock, patch

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message, KafkaChangeFeed
from corehq.apps.change_feed.data_sources import SOURCE_COUCH
from corehq.apps.change_feed.pillow import get_change_feed_pillow_for_db
from corehq.apps.es.cases import case_adapter
from corehq.util.elastic import ensure_index_deleted
from pillow_retry.api import process_pillow_retry
from pillow_retry.models import PillowError
from pillowtop.feed.couch import populate_change_metadata
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.sample import CountingProcessor
from testapps.test_pillowtop.utils import process_pillow_changes


class TestException(Exception):
    pass


class TestMixin(object):

    def _check_errors(self, expected_attempts, message=None):
        errors = list(PillowError.objects.filter(pillow=self.pillow.pillow_id).all())
        self.assertEqual(1, len(errors))

        self.assertEqual("pillow_retry.tests.test_retry.TestException", errors[0].error_type)
        self.assertEqual(expected_attempts, errors[0].total_attempts)
        self.assertEqual(expected_attempts, errors[0].current_attempt)

        if message:
            self.assertIn(message, errors[0].error_traceback)

        return errors


class CouchPillowRetryProcessingTest(TestCase, TestMixin):
    def setUp(self):
        super(CouchPillowRetryProcessingTest, self).setUp()
        self._fake_couch = FakeCouchDb()
        self._fake_couch.dbname = 'test_commcarehq'
        self.consumer = KafkaConsumer(
            topics.CASE_SQL,
            client_id='test-consumer',
            bootstrap_servers=settings.KAFKA_BROKERS,
            consumer_timeout_ms=100,
            enable_auto_commit=False,
        )
        try:
            next(self.consumer)
        except StopIteration:
            pass
        self.pillow = get_change_feed_pillow_for_db('fake-changefeed-pillow-id', self._fake_couch)
        self.original_process_change = self.pillow.process_change

    def tearDown(self):
        PillowError.objects.all().delete()
        self.consumer.close()
        super(CouchPillowRetryProcessingTest, self).tearDown()

    def test(self):
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'kafka-test-domain',
        }

        change = Change(id='test-id', sequence_id='3', document=document)
        populate_change_metadata(change, SOURCE_COUCH, self._fake_couch.dbname)

        with patch('pillow_retry.api.get_pillow_by_name', return_value=self.pillow):
            # first change creates error
            message = 'test retry 1'
            self.pillow.process_change = MagicMock(side_effect=TestException(message))
            self.pillow.process_with_error_handling(change)

            errors = self._check_errors(1, message)

            # second attempt updates error
            process_pillow_retry(errors[0])

            errors = self._check_errors(2)

            # third attempt successful
            self.pillow.process_change = self.original_process_change
            process_pillow_retry(errors[0])

            errors = list(PillowError.objects.filter(pillow=self.pillow.pillow_id).all())
            self.assertEqual(0, len(errors))

            message = next(self.consumer)

            change_meta = change_meta_from_kafka_message(message.value)
            self.assertEqual(SOURCE_COUCH, change_meta.data_source_type)
            self.assertEqual(self._fake_couch.dbname, change_meta.data_source_name)
            self.assertEqual('test-id', change_meta.document_id)
            self.assertEqual(document['doc_type'], change_meta.document_type)
            self.assertEqual(document['type'], change_meta.document_subtype)
            self.assertEqual(document['domain'], change_meta.domain)
            self.assertEqual(False, change_meta.is_deletion)


class KakfaPillowRetryProcessingTest(TestCase, TestMixin):

    def setUp(self):
        self.processor = CountingProcessor()
        self.pillow = ConstructedPillow(
            name='test-kafka-case-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(
                topics=[topics.CASE_SQL], client_id='test-kafka-case-feed'
            ),
            processor=self.processor
        )
        self.original_process_change = self.pillow.process_change

    def tearDown(self):
        ensure_index_deleted(case_adapter.index_name)

    def test(self):
        document = {
            '_id': 'test-id',
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'kafka-test-domain',
        }

        change = Change(id='test-id', sequence_id='3', document=document)
        populate_change_metadata(change, SOURCE_COUCH, 'test_commcarehq')

        with patch('pillow_retry.api.get_pillow_by_name', return_value=self.pillow):
            # first change creates error
            message = 'test retry 1'
            self.pillow.process_change = MagicMock(side_effect=TestException(message))
            self.pillow.process_with_error_handling(change)

            errors = self._check_errors(1, message)

            # second attempt updates error
            with process_pillow_changes(self.pillow):
                process_pillow_retry(errors[0])

            errors = self._check_errors(2)

            # third attempt successful
            self.pillow.process_change = self.original_process_change
            with process_pillow_changes(self.pillow):
                process_pillow_retry(errors[0])

            errors = list(PillowError.objects.filter(pillow=self.pillow.pillow_id).all())
            self.assertEqual(0, len(errors))

            self.assertEqual(1, self.processor.count)
