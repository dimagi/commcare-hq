from __future__ import absolute_import, unicode_literals
from csv342 import csv
import re
from datetime import datetime, timedelta

import os
from django.core.management import BaseCommand

from custom.icds_reports.tasks import get_dashboard_users_not_logged_in, get_inactive_cpmu
from io import open
from corehq.apps.users.models import CommCareUser

dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--user_list',
            action='store',
            dest='user_list',
            help='user list file location',
        )
        parser.add_argument(
            '--output-dir',
            action='store',
            default='',
            dest='output_dir',
            help='Output directory (defaults to the current directory)',
        )

    def handle(self, user_list, output_dir, *args, **kwargs):
        with open(user_list) as fin:
            users_names = fin.readlines()
            users_names = [user.strip() for user in users_names]
            end_date = datetime.utcnow()
            start_date_3_months = end_date - timedelta(days=90)
            not_logged_3_months = get_inactive_cpmu(start_date_3_months, end_date, users_names)
            week_file_name = 'dashboard_users_not_logged_in_{:%Y-%m-%d}_to_{:%Y-%m-%d}.csv'.format(
                start_date_3_months, end_date
            )
            output(not_logged_3_months, os.path.join(output_dir, week_file_name))


def output(usernames, path):
    with open(path, 'w') as out:
        writer = csv.writer(out)
        writer.writerow(["Username", "Location", "State"])
        for username in usernames:
            user = CommCareUser.get_by_username(username)
            loc = user.sql_location
            loc_name = loc.name if loc else ''
            state = loc.get_ancestor_of_type('state') if loc else None
            state_name = state.name if state else ''
            writer.writerow([username, loc_name, state_name])
