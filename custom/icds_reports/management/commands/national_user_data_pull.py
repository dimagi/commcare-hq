import csv

from django.core.management.base import BaseCommand
from corehq.apps.reports.util import get_all_users_by_domain
from custom.icds_reports.const import INDIA_TIMEZONE
from custom.icds_reports.models import ICDSAuditEntryRecord
from django.db.models import Max


class Command(BaseCommand):
    help = "Custom data pull"

    def convert_to_ist(self, date):
        if date is None:
            return 'N/A'
        date = date.astimezone(INDIA_TIMEZONE)
        date_formatted = date.strftime(date, "%d/%m/%Y, %I:%M %p")
        return date_formatted

    def handle(self, *args, **options):
        users = get_all_users_by_domain('icds-cas')
        usernames = []
        for user in users:
            if user.has_permission('icds-cas', 'access_all_locations'):
                usernames.append(user.username)
        usage_data = ICDSAuditEntryRecord.objects.filter(username__in=usernames).values('username').annotate(time=Max('time_of_use'))
        headers = ["S.No", "username", "time"]
        count = 1
        rows = [headers]
        usernames_usage = []
        for usage in usage_data:
            row_data = [
                count,
                usage.username,
                self.convert_to_ist(usage.time)
            ]
            usernames_usage.append(usage.username)
            rows.append(row_data)
            count = count + 1
        for user in usernames:
            if user not in usernames_usage:
                row_data = [
                    count,
                    user,
                    "N/A"
                ]
                rows.append(row_data)
                count = count + 1
        fout = open('/home/cchq/National_users_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(rows)
