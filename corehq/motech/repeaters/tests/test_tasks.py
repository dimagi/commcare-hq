from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.utils.xform import (
    FormSubmissionBuilder,
    TestFormMetadata,
)
from corehq.motech.models import ConnectionSettings, RequestLog

from ..const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
)
from ..models import FormRepeater, SQLRepeater
from ..tasks import process_repeater, delete_old_request_logs

DOMAIN = 'gaidhlig'
PAYLOAD_IDS = ['aon', 'dha', 'trì', 'ceithir', 'coig', 'sia', 'seachd', 'ochd',
               'naoi', 'deich']


class TestDeleteOldRequestLogs(TestCase):

    def tearDown(self):
        RequestLog.objects.filter(domain=DOMAIN).delete()

    def test_raw_delete_logs_old(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=91)
        log.save()  # Replace the value set by auto_now_add=True
        delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertEqual(count, 0)

    def test_raw_delete_logs_new(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=89)
        log.save()
        delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertGreater(count, 0)

    def test_num_queries_per_chunk(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=91)
        log.save()

        with self.assertNumQueries(5):
            delete_old_request_logs.apply()

    def test_num_queries_chunked(self):
        for __ in range(10):
            log = RequestLog.objects.create(domain=DOMAIN)
            log.timestamp = datetime.utcnow() - timedelta(days=91)
            log.save()

        with patch('corehq.motech.repeaters.tasks.DELETE_CHUNK_SIZE', 2):
            with self.assertNumQueries(21):
                delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertEqual(count, 0)


class TestProcessRepeater(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(DOMAIN)
        cls.connection_settings = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test API',
            url="http://localhost/api/"
        )
        cls.repeater = FormRepeater(
            domain=DOMAIN,
            connection_settings_id=cls.connection_settings.id,
        )
        cls.repeater.save()

    def setUp(self):
        self.sql_repeater = SQLRepeater.objects.create(
            domain=DOMAIN,
            repeater_id=self.repeater.get_id,
        )
        just_now = timezone.now() - timedelta(seconds=10)
        for payload_id in PAYLOAD_IDS:
            self.sql_repeater.repeat_records.create(
                domain=self.sql_repeater.domain,
                payload_id=payload_id,
                registered_at=just_now,
            )
            just_now += timedelta(seconds=1)

    def tearDown(self):
        self.sql_repeater.delete()

    @classmethod
    def tearDownClass(cls):
        cls.repeater.delete()
        cls.connection_settings.delete()
        cls.domain.delete()
        super().tearDownClass()

    def test_get_payload_fails(self):
        # If the payload of a repeat record is missing, it should be
        # cancelled, and process_repeater() should continue to the next
        # payload
        with patch('corehq.motech.repeaters.models.log_repeater_error_in_datadog'), \
                patch('corehq.motech.repeaters.tasks.metrics_counter'):
            process_repeater(self.sql_repeater)

        # All records were tried and cancelled
        records = list(self.sql_repeater.repeat_records.all())
        self.assertEqual(len(records), 10)
        self.assertTrue(all(r.state == RECORD_CANCELLED_STATE for r in records))
        # All records have a cancelled Attempt
        self.assertTrue(all(len(r.attempts) == 1 for r in records))
        self.assertTrue(all(r.attempts[0].state == RECORD_CANCELLED_STATE
                            for r in records))

    def test_send_request_fails(self):
        # If send_request() should be retried with the same repeat
        # record, process_repeater() should exit
        with patch('corehq.motech.repeaters.models.simple_post') as post_mock, \
                patch('corehq.motech.repeaters.tasks.metrics_counter'), \
                form_context(PAYLOAD_IDS):
            post_mock.return_value = Mock(status_code=400, reason='Bad request')
            process_repeater(self.sql_repeater)

        # Only the first record was attempted, the rest are still pending
        states = [r.state for r in self.sql_repeater.repeat_records.all()]
        self.assertListEqual(states, ([RECORD_FAILURE_STATE]
                                      + [RECORD_PENDING_STATE] * 9))


@contextmanager
def form_context(form_ids):
    for form_id in form_ids:
        builder = FormSubmissionBuilder(
            form_id=form_id,
            metadata=TestFormMetadata(domain=DOMAIN),
        )
        submit_form_locally(builder.as_xml_string(), DOMAIN)
    try:
        yield
    finally:
        FormAccessorSQL.hard_delete_forms(DOMAIN, form_ids)
