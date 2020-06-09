import json

from django.test import TestCase
from django.test.client import Client

from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, INCOMING
from corehq.apps.users.models import WebUser
from corehq.messaging.smsbackends.trumpia.models import TrumpiaBackend


class IncomingTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(IncomingTest, cls).setUpClass()
        cls.backend = TrumpiaBackend.objects.create(
            name="TRUMPIA",
            is_global=True,
            hq_api_id=TrumpiaBackend.get_api_id()
        )
        cls.domain = Domain(name='test')
        cls.domain.save()
        cls.phone_number = "7777722222"
        cls.couch_user = WebUser.create(cls.domain.name, "someone", "pw")
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
        self.client = Client()

    def test_activity_check(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "")

    def test_incoming(self):
        response, log = self.make_request("the message")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(log.text, "the message")
        self.assertEqual(log.phone_number, "+17777722222")
        self.assertEqual(log.direction, INCOMING)
        self.assertEqual(log.backend_message_id, "1234561234567asdf123")

    def test_incoming_non_nanp_number(self):
        response, log = self.make_request("the message", phone="0123456789")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(log.phone_number, "+0123456789")

    def test_incoming_non_nanp_number2(self):
        response, log = self.make_request("the message", phone="1234567890")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(log.phone_number, "+1234567890")

    def test_incoming_with_keyword(self):
        response, log = self.make_request("ca va", "REPLY")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(log.text, "ca va")
        self.assertEqual(log.direction, INCOMING)
        self.assertEqual(log.backend_message_id, "1234561234567asdf123")

    def make_request(self, message, keyword="", phone=None):
        xml = EXAMPLE_PUSH.format(
            phone_number=phone or self.phone_number,
            keyword=keyword,
            message=message,
        )
        response = self.client.get(self.path, {"xml": xml})
        message_id = json.loads(response.content)['message_id']
        return response, SMS.objects.get(couch_id=message_id)

    @property
    def path(self):
        return '/trumpia/sms/%s/' % self.backend.inbound_api_key


EXAMPLE_PUSH = """<?xml version="1.0" encoding="UTF-8" ?>
<TRUMPIA>
    <PUSH_ID>1234561234567asdf123</PUSH_ID>
    <INBOUND_ID>9996663330001</INBOUND_ID>
    <SUBSCRIPTION_UID>987987987980</SUBSCRIPTION_UID>
    <PHONENUMBER>{phone_number}</PHONENUMBER>
    <KEYWORD>{keyword}</KEYWORD>
    <CONTENTS><![CDATA[{message}]]></CONTENTS>
    <ATTACHMENT />
</TRUMPIA>
"""
