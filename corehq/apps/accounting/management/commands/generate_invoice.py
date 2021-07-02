from django.core.management import BaseCommand

from corehq.apps.accounting.invoicing import CustomerAccountInvoiceFactory
from corehq.apps.accounting.models import BillingAccount
from corehq.util.argparse_types import date_type


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('account_id', type=str, help="The billing account primary key")
        parser.add_argument('--startdate', required=True, type=date_type, help='Format YYYY-MM-DD')
        parser.add_argument('--enddate', required=True, type=date_type, help='Format YYYY-MM-DD')

    def handle(self, account_id, startdate, enddate, **options):
        account = BillingAccount.objects.get(pk=account_id)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=account,
            date_start=startdate,
            date_end=enddate
        )
        invoice_factory.create_invoice()
