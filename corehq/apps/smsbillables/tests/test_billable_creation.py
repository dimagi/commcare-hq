from datetime import datetime
from django.test import TestCase
from corehq.apps.sms.api import create_billable_for_sms
from corehq.apps.sms.models import SMSLog, OUTGOING
from corehq.apps.smsbillables.models import SmsBillable
from corehq.messaging.smsbackends.tropo.models import SQLTropoBackend


class TestBillableCreation(TestCase):

    def setUp(self):
        self.domain = 'sms_test_domain'
        self.mobile_backend = SQLTropoBackend(
            name="TEST",
            is_global=False,
            domain=self.domain,
            hq_api_id=SQLTropoBackend.get_api_id()
        )
        self.mobile_backend.save()
        self.text_short = "This is a test text message under 160 characters."
        self.text_long = (
            "This is a test text message that's over 160 characters in length. "
            "Or at least it will be. Thinking about kale. I like kale. Kale is "
            "a fantastic thing. Also bass music. I really like dat bass."
        )

    def _get_fake_sms(self, text):
        msg = SMSLog(
            domain=self.domain,
            phone_number='+16175555454',
            direction=OUTGOING,
            date=datetime.utcnow(),
            backend_id=self.mobile_backend.couch_id,
            text=text
        )
        msg.save()
        return msg

    def test_creation(self):
        msg = self._get_fake_sms(self.text_short)
        create_billable_for_sms(msg, delay=False)
        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=msg._id
        )
        self.assertEqual(sms_billables.count(), 1)

    def test_long_creation(self):
        msg = self._get_fake_sms(self.text_long)
        create_billable_for_sms(msg, delay=False)
        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=msg._id
        )
        self.assertEqual(sms_billables.count(), 2)

    def tearDown(self):
        self.mobile_backend.delete()
