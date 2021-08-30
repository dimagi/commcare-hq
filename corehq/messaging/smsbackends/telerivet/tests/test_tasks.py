from django.test import TestCase
from corehq.messaging.smsbackends.telerivet.tasks import process_message_status
from corehq.apps.sms.models import SMS
from ..const import DELIVERED, FAILED
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend


class TestProcessMessageStatus(TestCase):

    def setUp(self):
        super(TestProcessMessageStatus, self).setUp()
        self.backend = SQLTelerivetBackend(
            name='TELERIVET',
            is_global=True,
            hq_api_id=SQLTelerivetBackend.get_api_id()
        )
        self.backend.set_extra_fields(
            webhook_secret='The chamber of webhook secrets'
        )
        self.backend.save()

        self.sms = SMS(
            text='I am testy',
            custom_metadata={'case_id': '123'},
        )
        self.sms.save()

    def tearDown(self):
        self.sms.delete()
        super(TestProcessMessageStatus, self).tearDown()

    def test_status_delivered(self):
        process_message_status(self.sms, DELIVERED)

        sms = SMS.objects.get(couch_id=self.sms.couch_id)
        self.assertTrue('gateway_delivered' in sms.custom_metadata.keys())

    def test_error_status(self):
        message_id = self.sms.couch_id
        process_message_status(
            self.sms,
            FAILED,
            error_message='Somthing went wrong'
        )

        sms = SMS.objects.get(couch_id=message_id)
        self.assertTrue('gateway_delivered' not in sms.custom_metadata.keys())
