from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms
from corehq.apps.sms.models import SMS, QueuedSMS
from corehq.apps.sms.tasks import process_sms
from corehq.apps.sms.tests.util import BaseSMSTest, setup_default_sms_test_backend
from corehq.apps.smsbillables.models import SmsBillable
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from datetime import datetime
from dimagi.utils.couch.cache.cache_core import get_redis_client
from django.test.utils import override_settings
from mock import patch


@patch('corehq.apps.sms.management.commands.run_sms_queue.SMSEnqueuingOperation.enqueue_directly', autospec=True)
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
        SmsBillable.objects.filter(domain=self.domain).delete()
        QueuedSMS.objects.all().delete()
        SMS.objects.filter(domain=self.domain).delete()

    def tearDown(self):
        self.backend.delete()
        self.backend_mapping.delete()
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

        process_sms(queued_sms.pk)
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
