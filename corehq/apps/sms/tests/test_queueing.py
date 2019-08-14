from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms, incoming
from corehq.apps.sms.models import SMS, QueuedSMS
from corehq.apps.sms.tasks import process_sms, MAX_TRIAL_SMS, passes_trial_check
from corehq.apps.sms.tests.util import (
    BaseSMSTest,
    setup_default_sms_test_backend,
    delete_domain_phone_numbers
)
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.users.models import CommCareUser
from datetime import datetime, timedelta
from dimagi.utils.couch.cache.cache_core import get_redis_client
from django.conf import settings
from django.test.utils import override_settings
from mock import Mock, patch
from six.moves import range


def patch_datetime_api(timestamp):
    return patch('corehq.apps.sms.api.get_utcnow', new=Mock(return_value=timestamp))


def patch_datetime_tasks(timestamp):
    return patch('corehq.apps.sms.tasks.get_utcnow', new=Mock(return_value=timestamp))


def patch_successful_send():
    return patch('corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send')


def patch_failed_send():
    return patch(
        'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
        new=Mock(side_effect=Exception)
    )


def patch_error_send():
    def set_error(msg, *args, **kwargs):
        msg.set_system_error('Error')
    return patch(
        'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
        new=Mock(side_effect=set_error)
    )


@patch('corehq.apps.sms.management.commands.run_sms_queue.SMSEnqueuingOperation.enqueue', autospec=True)
@patch('corehq.apps.sms.tasks.process_sms.delay', autospec=True)
@override_settings(SMS_QUEUE_ENABLED=True)
class QueueingTestCase(BaseSMSTest):

    def setUp(self):
        super(QueueingTestCase, self).setUp()
        self.domain = 'test-sms-queueing'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()
        self.create_account_and_subscription(self.domain)
        self.domain_obj = Domain.get(self.domain_obj._id)
        self.backend, self.backend_mapping = setup_default_sms_test_backend()
        self.contact = CommCareUser.create(self.domain, 'user1', 'abc', phone_number='999123')
        entry = self.contact.get_or_create_phone_entry('999123')
        entry.set_two_way()
        entry.set_verified()
        entry.save()

        SmsBillable.objects.filter(domain=self.domain).delete()
        QueuedSMS.objects.all().delete()
        SMS.objects.filter(domain=self.domain).delete()

    def tearDown(self):
        self.contact.delete()
        self.backend.delete()
        self.backend_mapping.delete()

        delete_domain_phone_numbers(self.domain)
        SmsBillable.objects.filter(domain=self.domain).delete()
        QueuedSMS.objects.all().delete()
        SMS.objects.filter(domain=self.domain).delete()
        self.domain_obj.delete()

        super(QueueingTestCase, self).tearDown()

    @property
    def queued_sms_count(self):
        return QueuedSMS.objects.count()

    @property
    def reporting_sms_count(self):
        return SMS.objects.filter(domain=self.domain).count()

    def get_queued_sms(self):
        self.assertEqual(self.queued_sms_count, 1)
        return QueuedSMS.objects.all()[0]

    def get_reporting_sms(self):
        self.assertEqual(self.reporting_sms_count, 1)
        return SMS.objects.filter(domain=self.domain)[0]

    def assertBillableExists(self, msg_id, count=1):
        self.assertEqual(SmsBillable.objects.filter(log_id=msg_id).count(), count)

    def assertBillableDoesNotExist(self, msg_id):
        self.assertEqual(SmsBillable.objects.filter(log_id=msg_id).count(), 0)

    def test_outgoing(self, process_sms_delay_mock, enqueue_directly_mock):
        send_sms(self.domain, None, '+999123', 'test outgoing')

        self.assertEqual(enqueue_directly_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 1)
        self.assertEqual(self.reporting_sms_count, 0)

        queued_sms = self.get_queued_sms()
        self.assertEqual(queued_sms.domain, self.domain)
        self.assertEqual(queued_sms.phone_number, '+999123')
        self.assertEqual(queued_sms.text, 'test outgoing')
        self.assertEqual(queued_sms.processed, False)
        self.assertEqual(queued_sms.error, False)
        couch_id = queued_sms.couch_id
        self.assertIsNotNone(couch_id)

        with patch_successful_send() as send_mock:
            process_sms(queued_sms.pk)

        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 0)
        self.assertEqual(self.reporting_sms_count, 1)

        reporting_sms = self.get_reporting_sms()
        self.assertEqual(reporting_sms.domain, self.domain)
        self.assertEqual(reporting_sms.phone_number, '+999123')
        self.assertEqual(reporting_sms.text, 'test outgoing')
        self.assertEqual(reporting_sms.processed, True)
        self.assertEqual(reporting_sms.error, False)
        self.assertEqual(reporting_sms.couch_id, couch_id)
        self.assertEqual(reporting_sms.backend_api, self.backend.get_api_id())
        self.assertEqual(reporting_sms.backend_id, self.backend.couch_id)

        self.assertEqual(process_sms_delay_mock.call_count, 0)
        self.assertBillableExists(couch_id)

    def test_outgoing_failure(self, process_sms_delay_mock, enqueue_directly_mock):
        timestamp = datetime(2016, 1, 1, 12, 0)

        with patch_datetime_api(timestamp):
            send_sms(self.domain, None, '+999123', 'test outgoing')

        self.assertEqual(enqueue_directly_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 1)
        self.assertEqual(self.reporting_sms_count, 0)

        for i in range(settings.SMS_QUEUE_MAX_PROCESSING_ATTEMPTS):
            queued_sms = self.get_queued_sms()
            self.assertEqual(queued_sms.domain, self.domain)
            self.assertEqual(queued_sms.phone_number, '+999123')
            self.assertEqual(queued_sms.text, 'test outgoing')
            self.assertEqual(queued_sms.datetime_to_process, timestamp)
            self.assertEqual(queued_sms.processed, False)
            self.assertEqual(queued_sms.error, False)
            self.assertEqual(queued_sms.num_processing_attempts, i)

            with patch_failed_send() as send_mock, patch_datetime_tasks(timestamp + timedelta(seconds=1)):
                process_sms(queued_sms.pk)

            self.assertEqual(process_sms_delay_mock.call_count, 0)
            self.assertBillableDoesNotExist(queued_sms.couch_id)

            self.assertEqual(send_mock.call_count, 1)
            if i < (settings.SMS_QUEUE_MAX_PROCESSING_ATTEMPTS - 1):
                self.assertEqual(self.queued_sms_count, 1)
                self.assertEqual(self.reporting_sms_count, 0)
                timestamp += timedelta(minutes=settings.SMS_QUEUE_REPROCESS_INTERVAL)
            else:
                self.assertEqual(self.queued_sms_count, 0)
                self.assertEqual(self.reporting_sms_count, 1)

        reporting_sms = self.get_reporting_sms()
        self.assertEqual(reporting_sms.domain, self.domain)
        self.assertEqual(reporting_sms.phone_number, '+999123')
        self.assertEqual(reporting_sms.text, 'test outgoing')
        self.assertEqual(reporting_sms.processed, False)
        self.assertEqual(reporting_sms.error, True)
        self.assertEqual(reporting_sms.num_processing_attempts, settings.SMS_QUEUE_MAX_PROCESSING_ATTEMPTS)
        self.assertBillableDoesNotExist(reporting_sms.couch_id)

    def test_outgoing_failure_recovery(self, process_sms_delay_mock, enqueue_directly_mock):
        timestamp = datetime(2016, 1, 1, 12, 0)

        with patch_datetime_api(timestamp):
            send_sms(self.domain, None, '+999123', 'test outgoing')

        self.assertEqual(enqueue_directly_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 1)
        self.assertEqual(self.reporting_sms_count, 0)

        queued_sms = self.get_queued_sms()
        self.assertEqual(queued_sms.datetime_to_process, timestamp)
        self.assertEqual(queued_sms.processed, False)
        self.assertEqual(queued_sms.error, False)
        self.assertEqual(queued_sms.num_processing_attempts, 0)

        with patch_failed_send() as send_mock, patch_datetime_tasks(timestamp + timedelta(seconds=1)):
            process_sms(queued_sms.pk)

        self.assertEqual(process_sms_delay_mock.call_count, 0)
        self.assertBillableDoesNotExist(queued_sms.couch_id)
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 1)
        self.assertEqual(self.reporting_sms_count, 0)
        timestamp += timedelta(minutes=settings.SMS_QUEUE_REPROCESS_INTERVAL)

        queued_sms = self.get_queued_sms()
        self.assertEqual(queued_sms.datetime_to_process, timestamp)
        self.assertEqual(queued_sms.processed, False)
        self.assertEqual(queued_sms.error, False)
        self.assertEqual(queued_sms.num_processing_attempts, 1)

        with patch_successful_send() as send_mock, patch_datetime_tasks(timestamp + timedelta(seconds=1)):
            process_sms(queued_sms.pk)

        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 0)
        self.assertEqual(self.reporting_sms_count, 1)

        reporting_sms = self.get_reporting_sms()
        self.assertEqual(reporting_sms.processed, True)
        self.assertEqual(reporting_sms.error, False)
        self.assertEqual(reporting_sms.num_processing_attempts, 2)

        self.assertEqual(process_sms_delay_mock.call_count, 0)
        self.assertBillableExists(reporting_sms.couch_id)

    def test_outgoing_with_error(self, process_sms_delay_mock, enqueue_directly_mock):
        send_sms(self.domain, None, '+999123', 'test outgoing')

        self.assertEqual(enqueue_directly_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 1)
        self.assertEqual(self.reporting_sms_count, 0)

        queued_sms = self.get_queued_sms()
        self.assertEqual(queued_sms.processed, False)
        self.assertEqual(queued_sms.error, False)
        couch_id = queued_sms.couch_id
        self.assertIsNotNone(couch_id)

        with patch_error_send() as send_mock:
            process_sms(queued_sms.pk)

        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 0)
        self.assertEqual(self.reporting_sms_count, 1)

        reporting_sms = self.get_reporting_sms()
        self.assertEqual(reporting_sms.processed, False)
        self.assertEqual(reporting_sms.error, True)
        self.assertEqual(reporting_sms.couch_id, couch_id)
        self.assertEqual(reporting_sms.backend_api, self.backend.get_api_id())
        self.assertEqual(reporting_sms.backend_id, self.backend.couch_id)

        self.assertEqual(process_sms_delay_mock.call_count, 0)
        self.assertBillableDoesNotExist(couch_id)

    @patch.object(QueuedSMS, 'set_system_error')
    @patch('corehq.apps.sms.tasks.domain_is_on_trial')
    def test_passes_trial_check(self, domain_is_on_trial_patch, set_system_error_patch, delay_patch,
            enqueue_patch):

        client = get_redis_client()
        sms = QueuedSMS(domain='trial-project')
        domain_is_on_trial_patch.return_value = True
        key = 'sms-sent-on-trial-for-trial-project'

        # Test when key doesn't exist yet
        self.assertIsNone(client.get(key))
        self.assertTrue(passes_trial_check(sms))
        self.assertEqual(client.get(key), 1)
        self.assertGreater(client.ttl(key), 89 * 24 * 60 * 60)

        # Test with existing key
        self.assertTrue(passes_trial_check(sms))
        self.assertEqual(client.get(key), 2)
        self.assertGreater(client.ttl(key), 89 * 24 * 60 * 60)

        # Test when limit is exceeded
        client.set(key, MAX_TRIAL_SMS)
        self.assertFalse(passes_trial_check(sms))
        set_system_error_patch.assert_called_once()

        # Test when not on trial
        domain_is_on_trial_patch.return_value = False
        self.assertTrue(passes_trial_check(sms))

    def test_incoming(self, process_sms_delay_mock, enqueue_directly_mock):
        incoming('999123', 'inbound test', self.backend.get_api_id())

        self.assertEqual(enqueue_directly_mock.call_count, 1)
        self.assertEqual(self.queued_sms_count, 1)
        self.assertEqual(self.reporting_sms_count, 0)

        queued_sms = self.get_queued_sms()
        self.assertIsNone(queued_sms.domain)
        self.assertIsNone(queued_sms.couch_recipient_doc_type)
        self.assertIsNone(queued_sms.couch_recipient)
        self.assertEqual(queued_sms.phone_number, '+999123')
        self.assertEqual(queued_sms.text, 'inbound test')
        self.assertEqual(queued_sms.processed, False)
        self.assertEqual(queued_sms.error, False)
        self.assertEqual(queued_sms.backend_api, self.backend.get_api_id())
        couch_id = queued_sms.couch_id
        self.assertIsNotNone(couch_id)
        self.assertBillableDoesNotExist(couch_id)

        process_sms(queued_sms.pk)
        self.assertEqual(self.queued_sms_count, 0)
        self.assertEqual(self.reporting_sms_count, 1)

        reporting_sms = self.get_reporting_sms()
        self.assertEqual(reporting_sms.domain, self.domain)
        self.assertEqual(reporting_sms.couch_recipient_doc_type, self.contact.doc_type)
        self.assertEqual(reporting_sms.couch_recipient, self.contact.get_id)
        self.assertEqual(reporting_sms.phone_number, '+999123')
        self.assertEqual(reporting_sms.text, 'inbound test')
        self.assertEqual(reporting_sms.processed, True)
        self.assertEqual(reporting_sms.error, False)
        self.assertEqual(reporting_sms.backend_api, self.backend.get_api_id())
        self.assertEqual(reporting_sms.couch_id, couch_id)
        self.assertBillableExists(couch_id)
