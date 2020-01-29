import csv
import os
from collections import defaultdict
from functools import wraps

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.core.management.base import BaseCommand
from django.db.models import Count, IntegerField

from dimagi.utils.chunked import chunked
from django.db.models.functions import Cast

from corehq.apps.users.models import CouchUser
from corehq.util.argparse_types import date_type
from corehq.util.log import with_progress_bar
from custom.icds_reports.const import THR_REPORT_EXPORT
from custom.icds_reports.models import ICDSAuditEntryRecord
from custom.icds_reports.sqldata.exports.dashboard_usage import DashBoardUsage

prefix = 'dashboard_usage_data_'
REQUEST_DATA_CACHE = f'{prefix}tabular_data.csv'
CAS_DATA_CACHE = f'{prefix}cas_export_data.csv'


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


class Command(BaseCommand):
    def add_arguments(self, parser):
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
        parser.add_argument('domain')
        parser.add_argument('username', help='The username of the logged in user')

    def handle(self, start_date, end_date, domain, username, **options):
        print(f'fetching users data')

        user = CouchUser.get_by_username(username)
        usage_data = DashBoardUsage(couch_user=user, domain=domain).get_excel_data()[0][1]

        # fetching dashboard usage counts
        tab_usage_counts, tab_indicators_count, cas_counts = \
            self.get_dashboard_usage_counts(start_date, end_date, domain)

        username_state_mapping = self.get_tabular_data(usage_data, tab_usage_counts, tab_indicators_count)
        print(f'Request data written to file {REQUEST_DATA_CACHE}')
        self.get_cas_data(cas_counts, username_state_mapping)
        print(f'Request data written to file {CAS_DATA_CACHE}')

    def get_dashboard_usage_counts(self, start_date, end_date, domain):
        """
        :param start_date: start date of the filter
        :param end_date: end date of the filter
        :param domain
        :return: returns the counts of no of downloads of each and total reports for  all usernames
        """
        print(f'Compiling usage counts for users')
        tabular_user_counts = defaultdict(int)
        cas_user_counts = defaultdict(int)
        tabular_user_indicators = defaultdict(lambda: [0] * 10)

        urls = ['/a/' + domain + '/cas_export', '/a/' + domain + '/icds_export_indicator']
        query = list(
                ICDSAuditEntryRecord.objects.filter(url__in=urls, time_of_use__gte=start_date,
                                                    time_of_use__lte=end_date)
                .annotate(indicator=Cast(KeyTextTransform('indicator', 'post_data'), IntegerField()))
                .filter(indicator__lte=THR_REPORT_EXPORT).values('indicator', 'username', 'url')
                .annotate(count=Count('indicator')).order_by('username', 'indicator'))
        for record in query:
            if record['url'] == urls[0]:
                cas_user_counts[record['username'].split('@')[0]] += record['count']
            else:
                tabular_user_counts[record['username'].split('@')[0]] += record['count']
                tabular_user_indicators[record['username'].split('@')[0]][int(record['indicator']) - 1]\
                    = record['count']

        return tabular_user_counts, tabular_user_indicators, cas_user_counts

    def get_tabular_data(self, usage_data, tab_total_counts, tab_indicators_count):
        tab_data = list()
        extra_headers = ['Total', 'Child', 'Pregnant Women', 'Demographics', 'System Usage',
                         'AWC infrastructure', 'Child Growth Monitoring List', 'ICDS - CAS Monthly Register',
                         'AWW Performance Report', 'LS Performance Report', 'Take Home Ration']
        username_vs_state_name = defaultdict()
        print(f'Compiling request data for {len(usage_data)} users')
        headers = usage_data[0][:7]
        headers.extend(extra_headers)
        usage_data = usage_data[1:]
        for chunk in chunked(with_progress_bar(usage_data), 500):
            for data in chunk:
                username = data[4]
                indicator_count = tab_indicators_count[username]
                csv_row = data[:7]
                csv_row.append(tab_total_counts[username])
                csv_row.extend(indicator_count)
                tab_data.append(csv_row)
                if username not in username_vs_state_name.keys():
                    username_vs_state_name[username] = data[1]
        tab_data.insert(0, headers)
        _write_to_file(REQUEST_DATA_CACHE, tab_data)
        return username_vs_state_name

    def get_cas_data(self, cas_total_counts, username_state_mapping):
        sheet_headers = ['Sr.No', 'State/UT Name',
                         'No. of times CAS data export downloaded (December 2019)']
        cas_data = list()
        cas_data_dict = defaultdict(int)

        # converting usernames to state names
        for key, value in cas_total_counts.items():
            cas_data_dict[username_state_mapping[key]] += value

        # creating cas data
        serial = 0
        for key, value in cas_data_dict.items():
            serial += 1
            cas_data.append([serial, key, value])
        cas_data.insert(0, sheet_headers)
        _write_to_file(CAS_DATA_CACHE, cas_data)
