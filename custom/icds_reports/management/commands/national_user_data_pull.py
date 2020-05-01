import csv

from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser, WebUser
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
        print(f"==========={len(users)} Commcare Users======\n")
        web_users = WebUser.by_domain('icds-cas')
        print(f"==========={len(users)} Web Users======\n")
        usernames = []
        users_created_time = {}
        for user in users:
            if ((len(user.assigned_location_ids)==0 or 'cpmu' in user.username.lower() ) and user.has_permission('icds-cas', 'access_all_locations')):
                usernames.append(user.username)
                users_created_time.update({ user.username: user.created_on })
        for user in web_users:
            if ((len(user.assigned_location_ids)==0 or 'cpmu' in user.username.lower() ) and user.has_permission('icds-cas', 'access_all_locations')):
                usernames.append(user.username)
                if user.username not in  users_created_time.keys():
                    users_created_time.update({ user.username: user.created_on })
        usernames = list(set(usernames))
        print(f"==========={len(usernames)} Unique national users======\n")
        chunk_size = 100
        headers = ["username", "last_access_time", "created_on"]
        rows = [headers]
        usernames_usage = []
        for user_chunk in chunked(usernames, chunk_size):
            usage_data = ICDSAuditEntryRecord.objects.filter(username__in=list(user_chunk)).values('username').annotate(time=Max('time_of_use'))
            print(f"===========Executing chunk of {len(usage_data)}======\n")
            for usage in usage_data:
                row_data = [
                    usage['username'],
                    self.convert_to_ist(usage['time']),
                    self.convert_to_ist(users_created_time[usage['username']])
                ]
                usernames_usage.append(usage['username'])
                rows.append(row_data)
        users_not_logged_in = set(usernames) - set(usernames_usage)
        rows.extend([[user, 'N/A', self.convert_to_ist(users_created_time[usage['username']])] for user in users_not_logged_in])
        print(f"===========Total rows of {len(rows)}======\n")
        fout = open('/home/cchq/National_users_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(rows)
