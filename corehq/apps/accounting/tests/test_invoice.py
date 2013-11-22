from django.test import TestCase

from corehq.apps.accounting.models import (
    BillingAccount,
    Currency,
)


class TestInvoiceGeneration(TestCase):

    def setUp(self):
        self.currency = Currency(
            name="US Dollar",
            code="USD",
            symbol="$",
            rate_to_usd=1.0
        )
        self.currency.save()

        self.billing_account = BillingAccount(
            name="Save the Pythons",
            created_by="biyeun@dimagi.com",
            contact=self.billing_contact,
            currency=self.currency,
        )
        self.billing_account.save()

    def test_billing_account_created(self):
        fetched_account = BillingAccount.objects.get(name="Save the Pythons")
        self.assertIsNotNone(fetched_account)

    def tearDown(self):
        self.billing_account.delete()
        self.currency.delete()
