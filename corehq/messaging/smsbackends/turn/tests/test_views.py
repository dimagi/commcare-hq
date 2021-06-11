import json
from mock import patch
from django.test import Client, TestCase
from django.urls import reverse

from corehq.util.test_utils import flag_enabled
from corehq.messaging.smsbackends.turn.views import TurnIncomingSMSView
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sms.models import SQLMobileBackend
from corehq.messaging.smsbackends.turn.models import SQLTurnWhatsAppBackend

DOMAIN_NAME = 'test-domain'


class TestTurnIncomingSMSView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(DOMAIN_NAME)
        mobile_backend = SQLMobileBackend(
            domain=cls.domain.name,
            hq_api_id=SQLTurnWhatsAppBackend.get_api_id(),
            name='testy-sql-mobile-backend',
        )
        mobile_backend.save()

        cls.api_key = mobile_backend.inbound_api_key
        cls.view_path = TurnIncomingSMSView.urlname

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.post_data = self._get_post_data()

    def _get_post_data(self):
        message = {
            'id': 'my_unique_id',
            'from': '+27841236549',
            'type': 'text',
            'text': {
                'body': 'Dire Straits - Sultans Of Swing'
            }
        }

        return {'messages': [message]}

    @patch('corehq.messaging.smsbackends.turn.views.incoming_sms')
    def test_turn_flag_disabled(self, incoming_sms):
        response = self.client.post(
            reverse(self.view_path, kwargs={'api_key': self.api_key}),
            json.dumps(self.post_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(incoming_sms.called)

    @patch('corehq.messaging.smsbackends.turn.views.incoming_sms')
    @flag_enabled('TURN_IO_BACKEND')
    def test_turn_flag_enabled(self, incoming_sms):
        response = self.client.post(
            reverse(self.view_path, kwargs={'api_key': self.api_key}),
            json.dumps(self.post_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(incoming_sms.called)
