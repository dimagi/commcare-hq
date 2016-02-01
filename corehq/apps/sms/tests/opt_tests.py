from django.test import TestCase
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.sms.api import incoming, send_sms
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from corehq.apps.domain.models import Domain


class OptTestCase(BaseAccountingTest, DomainSubscriptionMixin):
    def setUp(self):
        super(OptTestCase, self).setUp()
        self.domain = "opt-test"

        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

        self.setup_subscription(self.domain_obj.name, SoftwarePlanEdition.ADVANCED)

        self.backend, self.backend_mapping = setup_default_sms_test_backend()

    def test_opt_out_and_opt_in(self):
        self.assertEqual(PhoneNumber.objects.count(), 0)

        incoming("99912345678", "stop", "GVI")
        self.assertEqual(PhoneNumber.objects.count(), 1)
        phone_number = PhoneNumber.objects.get(phone_number="99912345678")
        self.assertFalse(phone_number.send_sms)

        incoming("99912345678", "start", "GVI")
        self.assertEqual(PhoneNumber.objects.count(), 1)
        phone_number = PhoneNumber.objects.get(phone_number="99912345678")
        self.assertTrue(phone_number.send_sms)

    def test_sending_to_opted_out_number(self):
        self.assertEqual(PhoneNumber.objects.count(), 0)
        self.assertTrue(send_sms(self.domain, None, "999123456789", "hello"))

        incoming("999123456789", "stop", "GVI")
        self.assertEqual(PhoneNumber.objects.count(), 1)
        phone_number = PhoneNumber.objects.get(phone_number="999123456789")
        self.assertFalse(phone_number.send_sms)

        self.assertFalse(send_sms(self.domain, None, "999123456789", "hello"))

    def tearDown(self):
        self.backend_mapping.delete()
        self.backend.delete()
        self.domain_obj.delete()

        self.teardown_subscription()
