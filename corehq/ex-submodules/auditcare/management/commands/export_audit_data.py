import csv

from django.core.management.base import BaseCommand

from auditcare.utils.export import get_all_log_events, write_generic_log_event
from corehq.util.argparse_types import date_type


class Command(BaseCommand):
    help = """Export Audit data"""

    def add_arguments(self, parser):
        parser.add_argument('filename', help="Output file path")
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=date_type,
            help="The start date - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=date_type,
            help="The end date - format YYYY-MM-DD",
        )

    def handle(self, filename=None, **options):
        with open(filename, 'w') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Date', 'Type', 'User', 'Domain', 'IP Address', 'Action', 'Resource', 'Description'])
            for event in get_all_log_events(options['start'], options['end']):
                write_generic_log_event(writer, event)
