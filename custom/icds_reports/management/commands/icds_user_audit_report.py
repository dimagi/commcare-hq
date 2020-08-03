import csv

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import TruncDay

from corehq.util.argparse_types import date_type
from custom.icds_reports.models import ICDSAuditEntryRecord
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("usernames", help="CSV list of usernames")
        parser.add_argument(
            'start_date',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD'
        )
        parser.add_argument(
            'end_date',
            type=date_type,
            help='The end date (exclusive). format YYYY-MM-DD'
        )

    def handle(self, usernames, start_date, end_date, **options):
        usernames = usernames.split(',')

        writer = csv.writer(self.stdout)
        writer.writerow(['username', 'url', 'response code', 'date', 'request count'])

        for chunk in chunked(usernames, 50):
            query = (
                ICDSAuditEntryRecord.objects.values('username', 'url', 'response_code')
                .filter(username__in=chunk, time_of_use__gte=start_date, time_of_use__lte=end_date)
                .annotate(date=TruncDay('time_of_use'))
                .annotate(Count('username'))
            )
            for row in query:
                writer.writerow([
                    row['ip_address'],
                    row['username'],
                    row['url'],
                    row['response_code'],
                    row['date'],
                    row['username__count']
                ])
