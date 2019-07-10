from __future__ import absolute_import, unicode_literals
import csv342 as csv
import re
from datetime import datetime, timedelta

import os
from django.core.management import BaseCommand

from custom.icds_reports.tasks import get_dashboard_users_not_logged_in
from io import open
from corehq.apps.users.models import CommCareUser

dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            action='store',
            default='icds-cas',
            dest='domain',
            help='Domain (defaults to "icds-cas")',
        )
        parser.add_argument(
            '--output-dir',
            action='store',
            default='',
            dest='output_dir',
            help='Output directory (defaults to the current directory)',
        )

    def handle(self, domain, output_dir, *args, **kwargs):
        domain = domain

        end_date = datetime.utcnow()
        start_date_week = end_date - timedelta(days=7)
        not_logged_in_week = get_dashboard_users_not_logged_in(start_date_week, end_date, domain=domain)
        week_file_name = 'dashboard_users_not_logged_in_{:%Y-%m-%d}_to_{:%Y-%m-%d}.csv'.format(
            start_date_week, end_date
        )
        output(not_logged_in_week, os.path.join(output_dir, week_file_name))

        start_date_month = end_date - timedelta(days=30)
        not_logged_in_month = get_dashboard_users_not_logged_in(start_date_month, end_date, domain=domain)
        month_file_name = 'dashboard_users_not_logged_in_{:%Y-%m-%d}_to_{:%Y-%m-%d}.csv'.format(
            start_date_month, end_date
        )
        output(not_logged_in_month, os.path.join(output_dir, month_file_name))


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
