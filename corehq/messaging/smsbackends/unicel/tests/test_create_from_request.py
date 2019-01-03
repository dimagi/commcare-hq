from __future__ import absolute_import
from __future__ import unicode_literals

import codecs
from datetime import timedelta

from django.test import TestCase
from django.test.client import Client

from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, INCOMING
from corehq.apps.users.models import WebUser
from corehq.messaging.smsbackends.unicel.models import InboundParams, SQLUnicelBackend
import json


class IncomingPostTest(TestCase):

    INDIA_TZ_OFFSET = timedelta(hours=5.5)

    @classmethod
    def setUpClass(cls):
        super(IncomingPostTest, cls).setUpClass()
        cls.unicel_backend = SQLUnicelBackend.objects.create(
            name='UNICEL',
            is_global=True,
            hq_api_id=SQLUnicelBackend.get_api_id()
        )

    @classmethod
    def tearDownClass(cls):
        cls.unicel_backend.delete()
        super(IncomingPostTest, cls).tearDownClass()

    def setUp(self):
        self.domain = Domain(name='mockdomain')
        self.domain.save()
        SMS.by_domain(self.domain.name).delete()
        self.user = 'username-unicel'
        self.password = 'password'
        self.number = 5555551234
        self.couch_user = WebUser.create(self.domain.name, self.user, self.password)
        self.couch_user.add_phone_number(self.number)
        self.couch_user.save()
        self.message_ascii = 'It Works'
        self.message_utf_hex = '0939093F0928094D092609400020091509300924093E00200939094800200907093800200938092E092F00200915093E092E002009390948003F'

    def tearDown(self):
        self.couch_user.delete()
        self.domain.delete()

    def testPostToIncomingAscii(self):
        fake_post = {InboundParams.SENDER: str(self.number),
                     InboundParams.MESSAGE: self.message_ascii,
                     InboundParams.MID: '00001',
                     InboundParams.DCS: '0'}
        response, log = post(fake_post, self.unicel_backend)
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.message_ascii, log.text)
        self.assertEqual(INCOMING, log.direction)
        self.assertEqual(log.backend_message_id, fake_post[InboundParams.MID])

    def testPostToIncomingUtf(self):
        fake_post = {InboundParams.SENDER: str(self.number),
                     InboundParams.MESSAGE: self.message_utf_hex,
                     InboundParams.MID: '00002',
                     InboundParams.DCS: '8'}
        response, log = post(fake_post, self.unicel_backend)
        self.assertEqual(200, response.status_code)
        self.assertEqual(codecs.decode(codecs.decode(self.message_utf_hex, 'hex'), 'utf_16_be'),
                        log.text)
        self.assertEqual(INCOMING, log.direction)
        self.assertEqual(log.backend_message_id, fake_post[InboundParams.MID])


def post(data, backend):
    client = Client()
    response = client.get('/unicel/in/%s/' % backend.inbound_api_key, data)
    message_id = json.loads(response.content)['message_id']
    return response, SMS.objects.get(couch_id=message_id)
