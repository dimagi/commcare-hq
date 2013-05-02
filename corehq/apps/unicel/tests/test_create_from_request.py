from datetime import datetime, timedelta
from django.test import TestCase
from django.test.client import Client
from corehq.apps.sms.models import SMSLog, INCOMING
from corehq.apps.users.models import CouchUser, WebUser
from corehq.apps.unicel.api import InboundParams, DATE_FORMAT
import json

class IncomingPostTest(TestCase):

    INDIA_TZ_OFFSET = timedelta(hours=5.5)

    def setUp(self):
        self.domain = 'mockdomain'
        all_logs = SMSLog.by_domain_asc(self.domain).all()
        for log in all_logs:
            log.delete()
        self.user = 'username'
        self.password = 'password'
        self.number = 5555551234
        self.couch_user = WebUser.create(self.domain, self.user, self.password)
        self.couch_user.add_phone_number(self.number)
        self.couch_user.save()
        self.dcs = '8'
        self.message_ascii = 'It Works'
        self.message_utf_hex = '0939093F0928094D092609400020091509300924093E00200939094800200907093800200938092E092F00200915093E092E002009390948003F'

    def tearDown(self):
        self.couch_user.delete()

    def testPostToIncomingAscii(self):
        fake_post = {InboundParams.SENDER: str(self.number),
                     InboundParams.MESSAGE: self.message_ascii,
                     InboundParams.TIMESTAMP: datetime.now().strftime(DATE_FORMAT),
                     InboundParams.DCS: self.dcs,
                     InboundParams.UDHI: '0'}
        response, log = post(fake_post)
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.message_ascii, log.text)
        self.assertEqual(INCOMING, log.direction)
        self.assertEqual((log.date + self.INDIA_TZ_OFFSET).strftime(DATE_FORMAT),
                         fake_post[InboundParams.TIMESTAMP])


    def testPostToIncomingUtf(self):
        fake_post = {InboundParams.SENDER: str(self.number),
                     InboundParams.MESSAGE: self.message_utf_hex,
                     InboundParams.TIMESTAMP: datetime.now().strftime(DATE_FORMAT),
                     InboundParams.DCS: self.dcs,
                     InboundParams.UDHI: '1'}
        response, log = post(fake_post)
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.message_utf_hex.decode("hex").decode("utf_16_be"),
                        log.text)
        self.assertEqual(INCOMING, log.direction)
        self.assertEqual((log.date + self.INDIA_TZ_OFFSET).strftime(DATE_FORMAT),
                         fake_post[InboundParams.TIMESTAMP])

def post(data):
    client = Client()
    response = client.post('/unicel/in/', data)
    message_id = json.loads(response.content)['message_id']
    return response, SMSLog.get(message_id)
