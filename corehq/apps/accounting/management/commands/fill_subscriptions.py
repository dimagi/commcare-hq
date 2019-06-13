from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from django.core.management import BaseCommand
from corehq.apps.accounting.models import SoftwarePlanEdition

from corehq.apps.accounting.invoicing import should_create_invoice
from corehq.apps.accounting.models import CustomerInvoice
from six.moves import input

class Command(BaseCommand):
    help = 'find customer invoice without subscriptions details and correct the data'

    def handle(self, **kwargs):
        invoices = CustomerInvoice.objects.filter(subscriptions=None).all()
        self.permit_invoice_to_change(invoices)

        for invoice in invoices:
            invoice_subs = self.get_invoice_subscriptions(invoice)
            invoice.subscriptions.set(invoice_subs)
            invoice.save()
        print("Updated Invoices")

    def permit_invoice_to_change(self, invoices):
        print("Following invoices will be updated")
        for invoice in invoices:
            print("Customer Invoice ID: {}, Account Id : {}".format(invoice.id, invoice.account_id))

        choice = input('Do you want to continue updating these (y/n)')
        assert choice.startswith('y')

    def get_invoice_subscriptions(self, invoice):
        all_subscriptions = invoice.account.subscription_set.filter(do_not_invoice=False)
        return [
            sub for sub in all_subscriptions
            if (not sub.plan_version.plan.edition == SoftwarePlanEdition.COMMUNITY
                and should_create_invoice(sub, sub.subscriber.domain, invoice.date_start, invoice.date_end))
        ]




