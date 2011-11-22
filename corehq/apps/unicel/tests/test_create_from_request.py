from datetime import datetime
from django.test import TestCase
from django.test.client import Client
from corehq.apps.sms.models import MessageLog
from corehq.apps.users.models import CouchUser, WebUser
from corehq.apps.unicel.api import InboundParams, create_from_request

class IncomingPostTest(TestCase):

    def setUp(self):
        all_logs = MessageLog.all()
        for log in all_logs:
            log.delete()
        self.user = 'username'
        self.password = 'password'
        self.domain = 'mockdomain'
        self.number = 5555551234
        self.couch_user = WebUser.create(self.domain, self.user, self.password)
        self.couch_user.add_phone_number(self.number)
        self.couch_user.save()
        self.dcs = '8'
        self.message_ascii = 'Test Message'
        self.message_utf_hex = '0939093F0928094D092609400020091509300924093E00200939094800200907093800200938092E092F00200915093E092E002009390948003F'

    def tearDown(self):
        self.couch_user.delete()
        
    def testPostToIncomingAscii(self):
        fake_post = {InboundParams.SENDER: str(self.number),
                     InboundParams.MESSAGE: self.message_ascii,
                     InboundParams.TIMESTAMP: datetime.now().strftime("%m/%d/%Y %H:%M:%S %p"),
                     InboundParams.DCS: self.dcs,
                     InboundParams.UDHI: '0'}
        client = Client()
        response = client.post('/unicel/in/', fake_post)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, MessageLog.count_by_domain(self.domain))

    def testPostToIncomingUtf(self):
        fake_post = {InboundParams.SENDER: str(self.number),
                     InboundParams.MESSAGE: self.message_utf_hex,
                     InboundParams.TIMESTAMP: datetime.now().strftime("%m/%d/%Y %H:%M:%S %p"),
                     InboundParams.DCS: self.dcs,
                     InboundParams.UDHI: '2'}
        client = Client()
        response = client.get('/unicel/in/', fake_post)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, MessageLog.count_by_domain(self.domain))

