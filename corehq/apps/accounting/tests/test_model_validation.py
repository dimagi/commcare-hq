from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date

from django.core.exceptions import ValidationError

from corehq.apps.accounting.models import (
    BillingAccount,
    CreditAdjustment,
    Invoice,
    LineItem,
    Subscriber,
    Subscription,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest


class TestCreditAdjustmentValidation(BaseAccountingTest):

    def test_clean(self):
        account = BillingAccount.objects.create(
            name='Test Account',
            created_by='test@example.com',
            currency=generator.init_default_currency(),
        )
        subscription = Subscription.visible_objects.create(
            account=account,
            date_start=date.today(),
            plan_version=generator.subscribable_plan_version(),
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
