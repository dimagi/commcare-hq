import json

from django.test import TestCase
from django.test.client import Client

from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, INCOMING
from corehq.apps.users.models import WebUser
from corehq.messaging.smsbackends.starfish.models import StarfishBackend


class IncomingTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(IncomingTest, cls).setUpClass()
        cls.backend = StarfishBackend.objects.create(
            name='STARFISH',
            is_global=True,
            hq_api_id=StarfishBackend.get_api_id()
        )
        cls.domain = Domain(name='mockdomain')
        cls.domain.save()
        cls.phone_number = "255111222333"
        cls.couch_user = WebUser.create(cls.domain.name, "starfish", "pw")
        cls.couch_user.add_phone_number(cls.phone_number)
        cls.couch_user.save()

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        cls.domain.delete()
        cls.backend.delete()
        super(IncomingTest, cls).tearDownClass()

    def setUp(self):
        SMS.by_domain(self.domain.name).delete()

    def receiveMessage(self, message):
        data = {
            "msisdn": self.phone_number,
            "message": message.encode("utf-8"),
        }
        response, log = fake_request(data, self.backend)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(log.text, message)
        self.assertEqual(log.direction, INCOMING)

    def testIncomingAscii(self):
        self.receiveMessage("the message")

    def testIncomingUtf8(self):
        self.receiveMessage("\u4500")


def fake_request(data, backend):
    client = Client()
    response = client.get('/starfish/sms/%s/' % backend.inbound_api_key, data)
    message_id = json.loads(response.content)['message_id']
    return response, SMS.objects.get(couch_id=message_id)
