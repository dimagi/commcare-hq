from django.core.management.base import BaseCommand
from corehq.apps.accounting.models import Invoice
from django.db.models import Count


class Command(BaseCommand):
    help = 'Suppress duplicate invoices based on a given start date'

    def add_arguments(self, parser):
        parser.add_argument('invoice_start_date', type=str,
                            help='The start date of the invoices to be checked for duplicates')

    def handle(self, *args, **kwargs):
        invoice_start_date = kwargs['invoice_start_date']

        # Filter the Invoice objects based on the date_start
        invoices_of_given_date = Invoice.objects.filter(date_start=invoice_start_date)

        # Annotate the filtered queryset with a count of each subscription id
        duplicate_subscriptions = invoices_of_given_date.values('subscription').annotate(
            count=Count('id')).filter(count__gt=1)

        # Extract the subscription ids from the above queryset
        duplicate_subs_ids = [item['subscription'] for item in duplicate_subscriptions]

        suppressed_count = 0
        for sub_id in duplicate_subs_ids:
            related_invoices = Invoice.objects.filter(
                subscription_id=sub_id, date_start=invoice_start_date).order_by('-date_created')
            for invoice in related_invoices[1:]:
                invoice.is_hidden_to_ops = True
                invoice.save()
                suppressed_count += 1

        self.stdout.write(self.style.SUCCESS('Successfully suppressed {} duplicate invoices for date: {}'
                                             .format(suppressed_count, invoice_start_date)))
