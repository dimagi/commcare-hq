import csv
import re
from datetime import datetime, timedelta

import os
from django.core.management import BaseCommand

from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_id_username_pairs_by_domain
from corehq.apps.users.models import CommCareUser
from custom.icds_reports.models import ICDSAuditEntryRecord


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
        all_users = get_all_user_id_username_pairs_by_domain(domain, include_web_users=False,
                                                             include_mobile_users=True)
        all_dashboard_usernames = {
            uname
            for id, uname in all_users
            if dashboard_uname_rx.match(uname)
        }
        end_date = datetime.utcnow()
        start_date_week = end_date - timedelta(days=7)
        not_logged_in_week = get_dashboard_users_not_logged_in(start_date_week, end_date, all_dashboard_usernames)
        week_file_name = 'dashboard_users_not_logged_in_{:%Y-%m-%d}_to_{:%Y-%m-%d}.csv'.format(
            start_date_week, end_date
        )
        output(not_logged_in_week, os.path.join(output_dir, week_file_name))
        start_date_month = end_date - timedelta(days=30)
        not_logged_in_month = get_dashboard_users_not_logged_in(start_date_month, end_date,
                                                                all_dashboard_usernames)
        month_file_name = 'dashboard_users_not_logged_in_{:%Y-%m-%d}_to_{:%Y-%m-%d}.csv'.format(
            start_date_month, end_date
        )
        output(not_logged_in_month, os.path.join(output_dir, month_file_name))


def get_dashboard_users_not_logged_in(start_date, end_date, dashboard_usernames):
    logged_in = ICDSAuditEntryRecord.objects.filter(
        time_of_use__gte=start_date, time_of_use__lt=end_date
    ).values_list('username', flat=True)
    logged_in_dashboard_users = {
        u
        for u in logged_in
        if dashboard_uname_rx.match(u)
    }

    not_logged_in = dashboard_usernames - logged_in_dashboard_users
    return not_logged_in


def output(usernames, path):
    with open(path, 'w') as out:
        writer = csv.writer(out)
        writer.writerow(["Useranme", "Location", "State"])
        for username in usernames:
            user = CommCareUser.get_by_username(username)
            loc = user.sql_location
            loc_name = loc.name.encode('utf8') if loc else ''
            state = loc.get_ancestor_of_type('state') if loc else None
            state_name = state.name.encode('utf8') if state else ''
            writer.writerow([username, loc_name, state_name])
