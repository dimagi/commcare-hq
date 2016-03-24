from datetime import datetime, timedelta
from django.db import DatabaseError
from django.test import TestCase
from django.test.client import Client
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, INCOMING
from corehq.apps.users.models import CouchUser, WebUser
from corehq.messaging.smsbackends.unicel.models import InboundParams
import json

class IncomingPostTest(TestCase):

    INDIA_TZ_OFFSET = timedelta(hours=5.5)

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
        response, log = post(fake_post)
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.message_ascii, log.text)
        self.assertEqual(INCOMING, log.direction)
        self.assertEqual(log.backend_message_id, fake_post[InboundParams.MID])

    def testPostToIncomingUtf(self):
        fake_post = {InboundParams.SENDER: str(self.number),
                     InboundParams.MESSAGE: self.message_utf_hex,
                     InboundParams.MID: '00002',
                     InboundParams.DCS: '8'}
        response, log = post(fake_post)
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.message_utf_hex.decode("hex").decode("utf_16_be"),
                        log.text)
        self.assertEqual(INCOMING, log.direction)
        self.assertEqual(log.backend_message_id, fake_post[InboundParams.MID])


def post(data):
    client = Client()
    response = client.get('/unicel/in/', data)
    message_id = json.loads(response.content)['message_id']
    return response, SMS.objects.get(couch_id=message_id)
