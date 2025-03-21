from django.core.management.base import BaseCommand

from corehq.motech.repeaters.const import RECORD_QUEUED_STATES
from corehq.motech.repeaters.models import RepeatRecord


class Command(BaseCommand):
    help = 'Fire all repeaters in a domain.'

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        records = RepeatRecord.objects.filter(
            domain=domain,
            next_check__isnull=False,
            state__in=RECORD_QUEUED_STATES,
        )
        for record in records:
            record.fire(force_send=True)
            print('{} {}'.format(record.id, 'successful' if record.succeeded else 'failed'))
