from datetime import date

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase

from corehq.apps.accounting import generator
from corehq.apps.accounting.models import (
    BillingAccount,
    CreditAdjustment,
    Invoice,
    LineItem,
    Subscriber,
    Subscription,
)


class TestCreditAdjustmentValidation(TransactionTestCase):

    def tearDown(self):
        CreditAdjustment.objects.all().delete()
        LineItem.objects.all().delete()
        Invoice.objects.all().delete()
        generator.delete_all_subscriptions()
        generator.delete_all_accounts()
        super(TestCreditAdjustmentValidation, self).tearDown()

    def test_clean(self):
        account = BillingAccount.objects.create(
            currency=generator.init_default_currency(),
        )
        subscription = Subscription.objects.create(
            account=account,
            date_start=date.today(),
            plan_version=generator.subscribable_plan(),
            subscriber=Subscriber.objects.create(domain='test')
        )
        invoice = Invoice.objects.create(
            date_start=date.today(),
            date_end=date.today(),
            subscription=subscription,
        )
        line_item = LineItem.objects.create(
            invoice=invoice,
        )

        with self.assertRaises(ValidationError):
            try:
                CreditAdjustment(
                    invoice=invoice,
                    line_item=line_item,
                ).save()
            except ValidationError as e:
                self.assertIn('__all__', e.error_dict)
                raise e
