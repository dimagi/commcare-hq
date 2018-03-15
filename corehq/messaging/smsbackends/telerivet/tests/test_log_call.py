from __future__ import absolute_import
from __future__ import unicode_literals
import corehq.apps.ivr.tests.util as util
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from corehq.messaging.smsbackends.telerivet.tasks import EVENT_INCOMING, MESSAGE_TYPE_CALL
from django.test import Client


class TelerivetLogCallTestCase(util.LogCallTestCase):

    def setUp(self):
        super(TelerivetLogCallTestCase, self).setUp()
        self.backend = SQLTelerivetBackend(
            name='MOBILE_BACKEND_TELERIVET',
            is_global=True,
            hq_api_id=SQLTelerivetBackend.get_api_id()
        )
        self.backend.set_extra_fields(webhook_secret='abc')
        self.backend.save()

    def tearDown(self):
        self.backend.delete()
        super(TelerivetLogCallTestCase, self).tearDown()

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
