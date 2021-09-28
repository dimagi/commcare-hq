import datetime

from django.core.management.base import BaseCommand

from corehq.motech.repeaters.models import RepeatRecord


class Command(BaseCommand):
    help = 'Fire all repeaters in a domain.'

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        next_year = datetime.datetime.utcnow() + datetime.timedelta(days=365)
        records = RepeatRecord.all(domain=domain, due_before=next_year)  # Excludes succeeded and cancelled
        for record in records:
            record.fire(force_send=True)
            print('{} {}'.format(record._id, 'successful' if record.succeeded else 'failed'))
