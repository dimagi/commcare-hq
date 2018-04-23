from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf import settings
from django.test import TestCase
from fakecouch import FakeCouchDb
from kafka import KafkaConsumer
from kafka.common import KafkaUnavailableError
from mock import MagicMock, patch

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.data_sources import SOURCE_COUCH
from corehq.apps.change_feed.pillow import get_change_feed_pillow_for_db
from corehq.util.test_utils import trap_extra_setup
from pillow_retry.api import process_pillow_retry
from pillow_retry.models import PillowError
from pillowtop.feed.couch import populate_change_metadata
from pillowtop.feed.interface import Change


class TestException(Exception):
    pass


class RetryProcessingTest(TestCase):
    def setUp(self):
        self._fake_couch = FakeCouchDb()
        self._fake_couch.dbname = 'test_commcarehq'
        with trap_extra_setup(KafkaUnavailableError):
            self.consumer = KafkaConsumer(
                topics.CASE,
                group_id='test-consumer',
                bootstrap_servers=[settings.KAFKA_URL],
                consumer_timeout_ms=100,
            )
        self.pillow = get_change_feed_pillow_for_db('fake-changefeed-pillow-id', self._fake_couch)
        self.original_process_change = self.pillow.process_change
        PillowError.objects.all().delete()

    def test_couch_pillow(self):
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

            errors = list(PillowError.objects.filter(pillow=self.pillow.pillow_id).all())
            self.assertEqual(1, len(errors))
            self.assertEqual("pillow_retry.tests.test_retry.TestException", errors[0].error_type)
            self.assertIn(message, errors[0].error_traceback)
            self.assertEqual(1, errors[0].total_attempts)
            self.assertEqual(1, errors[0].current_attempt)

            # second attempt updates error
            self.pillow.process_change = MagicMock(side_effect=TestException(message))
            process_pillow_retry(errors[0])

            errors = list(PillowError.objects.filter(pillow=self.pillow.pillow_id).all())
            self.assertEqual(1, len(errors))
            self.assertEqual("pillow_retry.tests.test_retry.TestException", errors[0].error_type)
            self.assertEqual(2, errors[0].total_attempts)
            self.assertEqual(2, errors[0].current_attempt)

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
