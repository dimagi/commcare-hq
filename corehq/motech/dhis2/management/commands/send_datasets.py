from datetime import datetime

from django.core.management import BaseCommand

from corehq.motech.dhis2.tasks import send_datasets


class Command(BaseCommand):
    help = ('Send all datasets for a domain. Specify --send-date to send data '
            'for a DHIS2 period in the past.')

    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument('--send_date', help="YYYY-MM-DD")

    def handle(self, domain_name, **options):
        send_date = options.get('send_date', None)
        send_datasets.apply(args=[domain_name], kwargs={'send_now': True, 'date_to_send': send_date})
