# Use modern Python
from __future__ import unicode_literals, absolute_import, print_function

from optparse import make_option
from django.core.management import BaseCommand

from corehq.apps.accounting.models import Invoice, InvoiceBaseManager


class Command(BaseCommand):
    help = 'Hides the specified invoice(s) from showing on reports'

    option_list = BaseCommand.option_list + (
        make_option('-u', '--unhide',
                    action='store_true',
                    default=False,
                    dest='unhide',
                    help="Make invoice(s) visible to the operations team"
                         "that were previously suppressed."),
    )

    def handle(self, *args, **options):
        is_visible = options.get('unhide', False)

        for invoice_id in args:
            try:
                invoice = super(InvoiceBaseManager, Invoice.objects).get_queryset().get(pk=invoice_id)
            except Invoice.DoesNotExist:
                print("Invoice {} was not found".format(invoice_id))
                continue

            invoice.is_hidden_to_ops = not is_visible
            invoice.save()

            print("Invoice {} is {} the operations team".format(
                invoice_id,
                'visible to' if is_visible else 'hidden from'
            ))
