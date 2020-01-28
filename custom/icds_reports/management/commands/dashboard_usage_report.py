import csv
import os
from collections import defaultdict
from datetime import datetime
from functools import wraps

from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.core.management.base import BaseCommand
from django.db.models import Count, IntegerField

from dimagi.utils.chunked import chunked
from django.db.models.functions import Cast

from corehq.util.argparse_types import date_type
from corehq.util.log import with_progress_bar
from custom.icds_reports.const import THR_REPORT_EXPORT
from custom.icds_reports.models import ICDSAuditEntryRecord, AwcLocation
from custom.icds_reports.models.aggregate import DashboardUserActivityReport

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
    required_fields = ['state_id', 'state_name', 'district_id', 'district_name', 'block_id', 'block_name']
    location_types = ['state_id', 'district_id', 'block_id']
    user_level_list = ['State', 'District', 'Block']
    location_test_fields = ['state_is_test', 'district_is_test', 'block_is_test', 'supervisor_is_test',
                            'awc_is_test']

    roles = {
        '.nod': 'Nodal Officer',
        '.ncd': 'Consultant(Nutrition & Child Development)',
        '.bcc': 'Consultant (Behaviour Change Communication & Capacity Building)',
        '.sdc': 'Consultant (Social Development & Community Mobilization)',
        '.mne': 'Consultant (Monitoring & Evaluation and Decentralized Planning)',
        '.fm': 'Consultant (Financial Management)',
        '.shd': 'Consultant (Procurement) (State Helpdesk)',
        '.pa': 'Project Associate',
        '.acc': 'Accountant',
        '.cta': 'Central Training Agent',
        '.dhd': 'District Coordinator (District Helpdesk)',
        '.dpa': 'District Project Assistant',
        '.dc': 'District Collector',
        '.bhd': 'Block Coordinator (Block Helpdesk)',
        '.bpa': 'Block Project Assistant',
        '.dpo': 'District Programme Officer (DPO)',
        '.cdpo': 'Child Development Project Officer (CDPO)',

    }

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

    def get_user_vs_state_mapping_and_usernames(self, user_data):
        """
        :param user_data: Dashboard activity records
        :return: username vs state map and username vs location ids map
        """
        user_state_map = defaultdict(str)
        user_location_dict = defaultdict(list)

        for record in user_data:
            if record['state_id'] not in user_state_map:
                user_state_map[record['username']] = record['state_id']
            if record['username'] not in user_location_dict:
                user_location_dict[record['username']] = [record['state_id'], record['district_id'],
                                                          record['block_id'], record['user_level']]
        return user_state_map, user_location_dict

    def handle(self, start_date, end_date, domain, **options):
        print(f'fetching users data')

        user_data = list()
        date = datetime.now()
        # fetching the last available dashboard activity report
        while not user_data:
            user_data = self.get_activity_report_data(date)
            date -= relativedelta(days=1)
        # fetching username vs state_id map for cas export data and username vs location ids map
        user_state_map, usernames_location_map = self.get_user_vs_state_mapping_and_usernames(user_data)

        # fetching dashboard usage counts
        tab_usage_counts, tab_indicators_count, cas_counts =\
            self.get_dashboard_usage_counts(start_date, end_date, domain, usernames_location_map.keys(),
                                            user_state_map)
        location_type_filter = {
            'aggregation_level': 5
        }
        for test_location in self.location_test_fields:
            location_type_filter[test_location] = 0
        all_awc_locations = AwcLocation.objects.filter(**location_type_filter).values(*self.required_fields)

        # fetching location_is vs name mapping since dashboard activity table stores only location ids
        location_mapping = self.get_location_id_vs_name_mapping_from_queryset(all_awc_locations)

        self.get_tabular_data(usernames_location_map.keys(), tab_usage_counts, tab_indicators_count,
                              location_mapping, usernames_location_map)
        print(f'Request data written to file {REQUEST_DATA_CACHE}')
        self.get_cas_data(cas_counts)
        print(f'Request data written to file {CAS_DATA_CACHE}')

    def get_location_id_vs_name_mapping_from_queryset(self, results_queryset):
        """
        :param results_queryset: AwcLocation values queryset
        :return: location id to name mapping dict
        """
        location_id_name_mapping = defaultdict(str)

        for result in results_queryset:
            for location_type in self.location_types:
                if result[location_type] not in location_id_name_mapping.keys():
                    location_id_name_mapping[result[location_type]] =\
                        result[self.get_location_name_string_from_location_id(location_type)]
        return location_id_name_mapping

    def get_dashboard_usage_counts(self, start_date, end_date, domain, usernames, user_state_map):
        """
        :param start_date: start date of the filter
        :param end_date: end date of the filter
        :param domain
        :param usernames: list of usernames
        :param user_state_map: username vs state_id map
        :return: returns the counts of no of downloads of each and total reports for  all usernames
        """
        print(f'Compiling usage counts for {len(usernames)} users')
        tabular_user_counts = defaultdict(int)
        cas_user_counts = defaultdict(int)
        tabular_user_indicators = defaultdict(lambda: [0] * 10)

        urls = ['/a/' + domain + '/cas_export', '/a/' + domain + '/icds_export_indicator']
        for chunk in chunked(with_progress_bar(usernames), 500):
            query = (
                    ICDSAuditEntryRecord.objects.filter(url__in=urls,
                                                        username__in=chunk, time_of_use__gte=start_date,
                                                        time_of_use__lte=end_date)
                    .annotate(indicator=Cast(KeyTextTransform('indicator', 'post_data'), IntegerField()))
                        .filter(indicator__lte=THR_REPORT_EXPORT).values('indicator', 'username', 'url')
                    .annotate(count=Count('indicator')).order_by('username', 'indicator'))
            for record in query:
                if record['url'] == urls[0]:
                    cas_user_counts[user_state_map[record['username']]] += record['count']
                else:
                    tabular_user_counts[record['username']] += record['count']
                    tabular_user_indicators[record['username']][int(record['indicator']) - 1] = record['count']

        return tabular_user_counts, tabular_user_indicators, cas_user_counts

    def get_role_from_username(self, username):
        """
        :param username:
        :return: Role of the user bases on his username
        """
        for key, value in self.roles.items():
            if key.lower() in username:
                return value
        return 'N/A'

    def get_activity_report_data(self, date):
        """
        :param date: Date for which the report is needed
        :return:Returns a list of activity report records based on the filters
        """
        return list(DashboardUserActivityReport.objects.filter(date=date).values('username', 'state_id',
                                                                                 'district_id', 'block_id',
                                                                                 'user_level'))

    def get_location_name_string_from_location_id(self, location_id):
        return location_id.replace('_id', '_name')

    def get_tabular_data(self, usernames, tab_total_counts, tab_indicators_count, location_mapping,
                         user_location_mapping):
        sheet_headers = ['Sr.No', 'State/UT Name', 'District Name', 'Block Name', 'Username', 'Level',
                         'Role', 'Total', 'Child', 'Pregnant Women', 'Demographics', 'System Usage',
                         'AWC infrastructure', 'Child Growth Monitoring List', 'ICDS - CAS Monthly Register',
                         'AWW Performance Report', 'LS Performance Report', 'Take Home Ration']
        tab_data = list()

        print(f'Compiling request data for {len(usernames)} users')
        for chunk in chunked(with_progress_bar(usernames), 500):
            for username in chunk:
                indicator_count = tab_indicators_count[username]

                location_details = user_location_mapping[username]

                for index, value in enumerate(location_details):
                    if value != 'All' and index < 3:
                        location_details[index] = location_mapping[value]

                csv_row = [0, location_details[0], location_details[1],
                           location_details[2], username.split('@')[0],
                           self.user_level_list[location_details[3] - 1],
                           self.get_role_from_username(username), tab_total_counts[username]]

                csv_row.extend(indicator_count)
                tab_data.append(csv_row)

        tab_data = sorted(tab_data, key=lambda x: (x[1], x[2], x[3]))
        for index, data in enumerate(tab_data):
            data[0] += (index + 1)
        tab_data.insert(0, sheet_headers)
        _write_to_file(REQUEST_DATA_CACHE, tab_data)

    def get_cas_data(self, cas_total_counts):
        sheet_headers = ['Sr.No', 'State/UT Name',
                         'No. of times CAS data export downloaded (December 2019)']
        cas_data = list()
        # constructing the cas export data
        serial = 0
        for key, value in cas_total_counts.items():
            serial += 1
            cas_data.append([serial, key, value])

        cas_data.insert(0, sheet_headers)
        _write_to_file(CAS_DATA_CACHE, cas_data)
