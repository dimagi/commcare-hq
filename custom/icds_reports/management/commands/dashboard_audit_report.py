import csv
import os
from datetime import datetime, timezone
from functools import wraps

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db.models.functions import TruncDay

from custom.icds_reports.const import DASHBOARD_DOMAIN
from dimagi.utils.chunked import chunked

from corehq.apps.users.dbaccessors import get_user_docs_by_username
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import CouchUser, Permissions
from corehq.util.log import with_progress_bar
from custom.icds_reports.models import ICDSAuditEntryRecord

PERMISSION = 'custom.icds_reports.reports.reports.DashboardReport'

prefix = 'check_audit_data_'
USER_DATA_CACHE = f'{prefix}users.csv'
USER_NO_PERMISSION_CACHE = f'{prefix}users_no_permission.csv'
REQUEST_DATA_CACHE = f'{prefix}request_data.csv'


def cache_to_file(cache_name):
    def _outer(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            data = _get_from_file(cache_name)
            if not data:
                data = fn(*args, **kwargs)
                _write_to_file(cache_name, data)
            return data
        return _inner
    return _outer


class Command(BaseCommand):

    def handle(self, **options):
        domain = 'icds-cas'
        start_date = datetime(2019, 10, 3).replace(tzinfo=timezone.utc)
        users_without_permission = self.get_users_without_permission(domain, start_date)
        self.get_request_data(users_without_permission, start_date)
        print(f'Request data written to file {REQUEST_DATA_CACHE}')

    def get_request_data(self, usernames, start_date):
        print(f'Compiling request data for {len(usernames)} users')
        request_data = []
        for chunk in with_progress_bar(chunked(usernames, 50), prefix='\tProcessing'):
            query = (
                ICDSAuditEntryRecord.objects.values('username', 'url', 'response_code')
                .filter(~Q(url__contains='login'))
                .filter(username__in=chunk, time_of_use__gt=start_date)
                .annotate(date=TruncDay('time_of_use'))
                .annotate(Count('username'))
            )
            for row in query:
                request_data.append([
                    row['username'],
                    row['url'],
                    row['response_code'],
                    row['date'],
                    row['username__count']
                ])
        _write_to_file(REQUEST_DATA_CACHE, request_data)

    @cache_to_file(USER_NO_PERMISSION_CACHE)
    def get_users_without_permission(self, start_date):
        usernames = self.get_usernames(start_date)

        print(f'Filter {len(usernames)} users according to permission')
        permission_name = get_permission_name(Permissions.view_report)
        users_without_permission = []
        for chunk in with_progress_bar(chunked(usernames, 100), prefix='\tProcessing'):
            users = [CouchUser.wrap_correctly(doc) for doc in get_user_docs_by_username(chunk)]
            for user in users:
                if not user.has_permission(DASHBOARD_DOMAIN, permission_name, data=PERMISSION):
                    users_without_permission.append(user.username)

        return users_without_permission

    @cache_to_file(USER_DATA_CACHE)
    def get_usernames(self, start_date):
        print(f'Getting usernames who have accessed the Dashboard since {start_date}')
        query = (
            ICDSAuditEntryRecord.objects.values('username')
            .filter(~Q(url__contains='login'))
            .filter(time_of_use__gt=start_date)
            .annotate(Count('username'))
        )
        return [
            row['username']
            for row in query
        ]


def _get_from_file(filename):
    if os.path.exists(filename):
        print(f'Fetching data from file: {filename}')
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            return [
                r[0] if len(r) == 1 else r for r in list(reader)
            ]


def _write_to_file(filename, rows):
    print(f'Writing {len(rows)} to file {filename}')
    with open(filename, 'w') as f:
        writer = csv.writer(f)
        writer.writerows([
            r if isinstance(r, list) else [r] for r in rows
        ])
