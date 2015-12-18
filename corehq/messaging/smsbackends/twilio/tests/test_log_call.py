from corehq.apps.ivr.tests.util import LogCallTestCase
from corehq.messaging.smsbackends.twilio.views import IVR_RESPONSE
from django.test import Client


class TwilioLogCallTestCase(LogCallTestCase):
    def simulate_inbound_call(self, phone_number):
        return Client().post('/twilio/ivr/', {
            'From': phone_number,
            'CallSid': 'xyz',
        })

    def check_response(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, IVR_RESPONSE)
