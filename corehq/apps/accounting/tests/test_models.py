from django.db import models
from django.test import TestCase

from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, Currency, Subscription


class TestBillingAccount(TestCase):

    def setUp(self):
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.currency = generator.init_default_currency()
        self.billing_account = generator.billing_account(self.dimagi_user, self.billing_contact)

    def test_creation(self):
        self.assertIsNotNone(self.billing_account)

    def test_deletions(self):
        self.assertRaises(models.ProtectedError, self.currency.delete)

    def tearDown(self):
        self.billing_contact.delete()
        self.dimagi_user.delete()
        BillingAccount.objects.all().delete()
        Currency.objects.all().delete()
