from django.test import TestCase
from corehq.messaging.smsbackends.telerivet.tasks import process_message_status
from corehq.apps.sms.models import SMS
from ..const import DELIVERED, FAILED


class TestProcessMessageStatus(TestCase):

    def setUp(self):
        super(TestProcessMessageStatus, self).setUp()
        self.sms = SMS(
            text='I am testy',
            custom_metadata={'case_id': '123'},
        )
        self.sms.save()

    def tearDown(self):
        self.sms.delete()
        super(TestProcessMessageStatus, self).tearDown()

    def test_status_delivered(self):
        message_id = self.sms.couch_id
        process_message_status(message_id, DELIVERED)

        sms = SMS.objects.get(couch_id=message_id)
        self.assertTrue('gateway_delivered' in sms.custom_metadata.keys())

    def test_error_status(self):
        message_id = self.sms.couch_id
        process_message_status(message_id, FAILED, error_message='Somthing went wrong')

        sms = SMS.objects.get(couch_id=message_id)
        self.assertTrue('gateway_delivered' not in sms.custom_metadata.keys())
