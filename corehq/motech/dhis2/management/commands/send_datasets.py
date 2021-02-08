from datetime import datetime

from django.core.management import BaseCommand

from corehq.motech.dhis2.tasks import send_datasets


class Command(BaseCommand):
    help = ('Manually send datasets for a domain. Specify --send-date '
            'to simulate a date in the past')

    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument('--send_date', help="YYYY-MM-DD")

    def handle(self, domain_name, **options):
        if 'send_date' in options:
            send_date = datetime.strptime(options['send_date'], '%Y-%m-%d')
        else:
            send_date = None
        print("Sending dataset")
        send_datasets.apply(domain_name, kwargs={
            'send_now': True, 'send_date': send_date,
        })
