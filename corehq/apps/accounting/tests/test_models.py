from django.db import models
from django.test import TestCase

from corehq.apps.accounting import generator


class TestBillingAccount(TestCase):

    def setUp(self):
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user()
        self.currency = generator.currency_usd()

    # todo: validation testing

    def test_deletions(self):
        billing_account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.assertRaises(models.ProtectedError, self.currency.delete)
        billing_account.delete()

    def tearDown(self):
        self.billing_contact.delete()
        self.dimagi_user.delete()
        self.currency.delete()
