from corehq.apps.ivr.tests.util import LogCallTestCase
from corehq.messaging.smsbackends.telerivet.models import TelerivetBackend
from corehq.messaging.smsbackends.telerivet.tasks import EVENT_INCOMING, MESSAGE_TYPE_CALL
from django.test import Client


class TelerivetLogCallTestCase(LogCallTestCase):
    def setUp(self):
        super(TelerivetLogCallTestCase, self).setUp()
        self.backend = TelerivetBackend(
            _id='MOBILE_BACKEND_TELERIVET',
            name='MOBILE_BACKEND_TELERIVET',
            webhook_secret='abc',
            is_global=True
        )
        self.backend.save()

    def tearDown(self):
        super(TelerivetLogCallTestCase, self).tearDown()
        self.backend.delete()

    def simulate_inbound_call(self, phone_number):
        return Client().post('/telerivet/in/', {
            'secret': 'abc',
            'from_number_e164': phone_number,
            'event': EVENT_INCOMING,
            'message_type': MESSAGE_TYPE_CALL,
            'id': 'xyz',
        })

    def check_response(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '')
