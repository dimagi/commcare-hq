from django.core.management.base import BaseCommand

import dateutil.parser

from ...utils.export import write_export_from_all_log_events


class Command(BaseCommand):
    help = """Export Audit data"""

    def add_arguments(self, parser):
        parser.add_argument('filename', help="Output file path")
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=dateutil.parser.parse,
            help="The start date - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=dateutil.parser.parse,
            help="The end date - format YYYY-MM-DD",
        )

    def handle(self, filename=None, **options):
        with open(filename, 'w') as csvfile:
            write_export_from_all_log_events(csvfile, start=options['start'], end=options['end'])
