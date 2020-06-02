import csv
from collections import defaultdict

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.core.management.base import BaseCommand
from django.db.models import Count, TextField

from dimagi.utils.chunked import chunked
from django.db.models.functions import Cast

from corehq.apps.users.models import CouchUser
from corehq.util.argparse_types import date_type
from corehq.util.log import with_progress_bar
from custom.icds_reports.const import THR_REPORT_EXPORT
from custom.icds_reports.models import ICDSAuditEntryRecord
from custom.icds_reports.sqldata.exports.dashboard_usage import DashBoardUsage

prefix = 'dashboard_usage_data_'
TABULAR_DATA_CACHE = f'{prefix}tabular_data.csv'
CAS_DATA_CACHE = f'{prefix}cas_export_data.csv'


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

        # fetching username to state mapping
        username_vs_state_name = defaultdict()
        for data in usage_data[1:]:
            username = data[4]
            state_name = data[1]
            username_vs_state_name[username] = state_name

        self.get_tabular_data(usage_data, start_date, end_date, domain)
        print(f'Request data written to file {TABULAR_DATA_CACHE}')
        self.get_cas_data(username_vs_state_name, start_date, end_date, domain)
        print(f'Request data written to file {CAS_DATA_CACHE}')

    def get_dashboard_tabular_usage_counts(self, start_date, end_date, domain):
        """
        :param start_date: start date of the filter
        :param end_date: end date of the filter
        :param domain
        :return: returns the counts of no of downloads of each and total reports for  all usernames
        """
        print(f'Compiling tabular usage counts for users')
        tabular_user_counts = defaultdict(int)
        tabular_user_indicators = defaultdict(lambda: [0] * 10)

        records = list(ICDSAuditEntryRecord.objects.filter(url=f'/a/{domain}/icds_export_indicator',
                                                           time_of_use__gte=start_date,
                                                           time_of_use__lt=end_date)
                       .annotate(indicator=Cast(KeyTextTransform('indicator', 'post_data'), TextField()))
                       .filter(indicator__lte=THR_REPORT_EXPORT).values('indicator', 'username')
                       .annotate(count=Count('indicator')).order_by('username', 'indicator'))
        for record in records:
            if record['indicator'] == '':
                continue
            tabular_user_counts[record['username'].split('@')[0]] += record['count']
            tabular_user_indicators[record['username'].split('@')[0]][int(record['indicator']) - 1]\
                = record['count']

        return tabular_user_counts, tabular_user_indicators

    def get_dashboard_cas_usage_counts(self, start_date, end_date, domain):
        """
        :param start_date: start date of the filter
        :param end_date: end date of the filter
        :param domain
        :return: returns the counts of no of downloads of each and total reports for  all usernames
        """
        print(f'Compiling cas export usage counts for users')
        cas_user_counts = defaultdict(int)

        records = list(ICDSAuditEntryRecord.objects.filter(url=f'/a/{domain}/cas_export',
                                                           time_of_use__gte=start_date,
                                                           time_of_use__lt=end_date)
                       .annotate(indicator=Cast(KeyTextTransform('indicator', 'post_data'), TextField()))
                       .values('indicator')
                       .annotate(count=Count('indicator')).values('username', 'count').order_by('username'))
        for record in records:
            cas_user_counts[record['username'].split('@')[0]] += record['count']
        return cas_user_counts

    def get_tabular_data(self, usage_data, start_date, end_date, domain):
        tab_data = list()

        tab_usage_counts, tab_indicators_count = \
            self.get_dashboard_tabular_usage_counts(start_date, end_date, domain)

        extra_headers = ['Total', 'Child', 'Pregnant Women', 'Demographics', 'System Usage',
                         'AWC infrastructure', 'Child Growth Monitoring List', 'ICDS - CAS Monthly Register',
                         'AWW Performance Report', 'LS Performance Report', 'Take Home Ration']
        print(f'Compiling request data for {len(usage_data)} users')
        headers = usage_data[0][:7]
        headers.extend(extra_headers)
        usage_data = usage_data[1:]
        for chunk in chunked(with_progress_bar(usage_data), 500):
            for data in chunk:
                username = data[4]
                indicator_count = tab_indicators_count[username]
                csv_row = data[:7]
                csv_row.append(tab_usage_counts[username])
                csv_row.extend(indicator_count)
                tab_data.append(csv_row)

        tab_data.insert(0, headers)
        _write_to_file(TABULAR_DATA_CACHE, tab_data)

    def get_cas_data(self, username_state_mapping, start_date, end_date, domain):
        cas_total_counts = self.get_dashboard_cas_usage_counts(start_date, end_date, domain)
        sheet_headers = ['Sr.No', 'State/UT Name',
                         f'No. of times CAS data export downloaded ({start_date.strftime("%m-%d-%Y")} to {end_date.strftime("%m-%d-%Y")})']
        cas_data = list()
        cas_data_dict = defaultdict(int)

        # converting usernames to state names
        for key, value in cas_total_counts.items():
            if key in username_state_mapping:
                cas_data_dict[username_state_mapping[key]] += value

        # creating cas data
        serial = 0
        for key, value in cas_data_dict.items():
            serial += 1
            cas_data.append([serial, key, value])
        cas_data.insert(0, sheet_headers)
        _write_to_file(CAS_DATA_CACHE, cas_data)
