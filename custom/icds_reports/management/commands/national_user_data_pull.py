import csv

from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser, WebUser
from custom.icds_reports.const import INDIA_TIMEZONE
from custom.icds_reports.models import ICDSAuditEntryRecord
from django.db.models import Max
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "List of users with national level access on Dashboard along with usage"

    def convert_to_ist(self, date):
        if date is None:
            return 'N/A'
        date = date.astimezone(INDIA_TIMEZONE)
        date_formatted = date.strftime("%d-%m-%Y")
        return date_formatted

    def _get_details(self, users, usernames, user_details):
        """
        :param users: user objects of all commcare and web users
        :param usernames: username array eg. [username1, username2]
        :param user_details: details dict contains created and role name eg.{username: [created_on, role_name]}
        :return: usernames and user_details dict
        """
        for user in users:
            role = user.get_role('icds-cas')
            if (role in ('CPMU','Dashboard Only Access', 'TRP') or len(user.assigned_location_ids)==0) and user.has_permission('icds-cas', 'access_all_locations'):
                usernames.append(user.username)
                user_details.update({ user.username: [ user.created_on, role.name ]})
        return usernames, user_details


    def handle(self, *args, **options):
        users = CommCareUser.by_domain('icds-cas')
        web_users = WebUser.by_domain('icds-cas')
        usernames = []
        user_details = {}
        usernames, user_details = self._get_details(users, usernames, user_details)
        usernames, user_details = self._get_details(web_users, usernames, user_details)
        usernames = list(set(usernames))
        chunk_size = 100
        headers = ["username", "last_access_time", "created_on", "role"]
        rows = [headers]
        usernames_usage = []
        for user_chunk in chunked(usernames, chunk_size):
            usage_data = ICDSAuditEntryRecord.objects.filter(
                username__in=list(user_chunk)).values('username').annotate(time=Max('time_of_use'))
            for usage in usage_data:
                row_data = [
                    usage['username'],
                    self.convert_to_ist(usage['time']),
                    self.convert_to_ist(user_details[usage['username']][0]),
                    user_details[usage['username']][1]
                ]
                usernames_usage.append(usage['username'])
                rows.append(row_data)
        users_not_logged_in = set(usernames) - set(usernames_usage)
        for user in users_not_logged_in:
            rows.extend([
                user,
                'N/A',
                self.convert_to_ist(user_details[usage['username']][0]),
                user_details[usage['username']][1]
            ])
        fout = open('/home/cchq/National_users_usage_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(rows)
