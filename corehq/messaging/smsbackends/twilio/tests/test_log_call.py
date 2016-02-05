from corehq.apps.ivr.tests.util import LogCallTestCase
from corehq.apps.sms.models import CallLog
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.messaging.smsbackends.twilio.views import IVR_RESPONSE
from django.test import Client


class TwilioLogCallTestCase(LogCallTestCase):
    def setUp(self):
        super(TwilioLogCallTestCase, self).setUp()
        self.backend = SQLTwilioBackend.objects.create(
            name='TWILIO',
            is_global=True,
            hq_api_id=SQLTwilioBackend.get_api_id()
        )

    def tearDown(self):
        self.backend.delete()
        super(TwilioLogCallTestCase, self).tearDown()

    def test_401_response(self):
        start_count = CallLog.count_by_domain(self.domain)

        response = Client().post('/twilio/ivr/xxxxx', {
            'From': self.phone_number,
            'CallSid': 'xyz',
        })
        self.assertEqual(response.status_code, 401)

        end_count = CallLog.count_by_domain(self.domain)
        self.assertEqual(start_count, end_count)

    def simulate_inbound_call(self, phone_number):
        url = '/twilio/ivr/%s' % self.backend.inbound_api_key
        return Client().post(url, {
            'From': phone_number,
            'CallSid': 'xyz',
        })

    def check_response(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, IVR_RESPONSE)
