from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from corehq.apps.sms.models import SMS
from django.test import TestCase
from django.urls import reverse


class TelerivetViewTestCase(TestCase):

    view_path = 'telerivet_message_status'

    def setUp(self):
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
            phone_number='27845698785',
            text="Fame is fickle"
        )
        self.sms.save()

    def tearDown(self):
        self.backend.delete()
        self.sms.delete()

    def test_message_status_successful(self):
        data = {'status': 'delivered', 'secret': self.backend.config.webhook_secret}
        response = self.client.post(reverse(self.view_path, kwargs={'message_id': self.sms.couch_id}), data)

        self.assertTrue(response.status_code, 200)
        self.sms.refresh_from_db()

        self.assertEqual(self.sms.custom_metadata, {'gateway_delivered': True})

    def test_message_status_unsuccessful(self):
        self.sms.custom_metadata = {}
        self.sms.save()

        data = {'status': 'delivered', 'secret': 'Trolls wander the forests'}
        response = self.client.post(reverse(self.view_path, kwargs={'message_id': self.sms.couch_id}), data)

        self.assertTrue(response.status_code, 200)
        self.sms.refresh_from_db()

        self.assertEqual(self.sms.custom_metadata, {})
