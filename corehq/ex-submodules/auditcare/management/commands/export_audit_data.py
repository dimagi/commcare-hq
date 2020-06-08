from django.core.management.base import BaseCommand

from auditcare.utils.export import write_export_from_all_log_events
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
            write_export_from_all_log_events(csvfile, start=options['start'], end=options['end'])
