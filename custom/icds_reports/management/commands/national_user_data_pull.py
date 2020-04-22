import csv

from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser
from custom.icds_reports.const import INDIA_TIMEZONE
from custom.icds_reports.models import ICDSAuditEntryRecord
from django.db.models import Max
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "Custom data pull"

    def convert_to_ist(self, date):
        if date is None:
            return 'N/A'
        date = date.astimezone(INDIA_TIMEZONE)
        date_formatted = date.strftime("%d/%m/%Y, %I:%M %p")
        return date_formatted

    def handle(self, *args, **options):
        users = CommCareUser.by_domain('icds-cas')
        usernames = []
        for user in users:
            if user.has_permission('icds-cas', 'access_all_locations'):
                usernames.append(user.username)
        chunk_size = 100
        headers = ["username", "time"]
        rows = [headers]
        usernames_usage = []
        for user_chunk in chunked(usernames, chunk_size):
            usage_data = ICDSAuditEntryRecord.objects.filter(username__in=list(user_chunk)).values('username').annotate(time=Max('time_of_use'))
            for usage in usage_data:
                print(usage)
                row_data = [
                    usage['username'],
                    self.convert_to_ist(usage['time'])
                ]
                usernames_usage.append(usage['username'])
                rows.append(row_data)
        users_not_logged_in = set(usernames) - set(usernames_usage)
        rows.extend([[user, 'N/A'] for user in users_not_logged_in])
        fout = open('/home/cchq/National_users_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(rows)
