from corehq.apps.ivr.tests.util import LogCallTestCase
from django.test import Client
import json


class TropoLogCallTestCase(LogCallTestCase):
    def simulate_inbound_call(self, phone_number):
        return Client().post(
            '/tropo/ivr/',
            json.dumps({'session': {'from': {'id': phone_number}}}),
            content_type='application/json'
        )

    def check_response(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '{"tropo": [{"reject": {}}]}')
