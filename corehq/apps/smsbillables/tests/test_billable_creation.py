from django.conf import settings
from django.test import TestCase
from corehq.apps.sms.api import send_sms_with_backend_name
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.tropo.api import TropoBackend


class TestBillableCreation(TestCase):

    def setUp(self):
        self.domain = 'sms_test_domain'
        self.mobile_backend = TropoBackend(
            name="TEST",
            domain=self.domain,
            messaging_token="12345679",
        )
        self.mobile_backend.save()
        self.phone_number = '+16175005454'
        self.text_short = "This is a test text message under 160 characters."
        self.text_long = (
            "This is a test text message that's over 160 characters in length. "
            "Or at least it will be. Thinking about kale. I like kale. Kale is "
            "a fantastic thing. Also bass music. I really like dat bass."
        )

    def test_creation(self):
        msg = send_sms_with_backend_name(
            self.domain, self.phone_number, self.text_short,
            self.mobile_backend.name, is_test=True
        )
        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=msg._id
        )
        self.assertEqual(sms_billables.count(), 1)

    def test_long_creation(self):
        msg = send_sms_with_backend_name(
            self.domain, self.phone_number, self.text_long,
            self.mobile_backend.name, is_test=True
        )
        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=msg._id
        )
        self.assertEqual(sms_billables.count(), 2)

    def tearDown(self):
        self.mobile_backend.delete()
