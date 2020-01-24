import csv
import os
import re
from collections import defaultdict
from datetime import timezone
from functools import wraps

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.core.management.base import BaseCommand
from django.db.models import Count

from dimagi.utils.chunked import chunked

from corehq.util.argparse_types import date_type
from corehq.util.log import with_progress_bar
from custom.icds_reports.models import ICDSAuditEntryRecord, AwcLocation

prefix = 'dashboard_usage_data_'
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
    required_fields = ['state_id', 'state_name', 'district_id', 'district_name', 'block_id', 'block_name']
    location_types = ['state_id', 'district_id', 'block_id']
    agg_required_fields = ['state_id', 'district_id', 'block_id', 'is_launched']
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

    def handle(self, start_date, end_date, **options):
        domain = 'icds-cas'
        start_date = start_date.replace(tzinfo=timezone.utc)
        end_date = end_date.replace(tzinfo=timezone.utc)

        print(f'fetching users data')
        all_users = self.get_users(domain)
        dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')
        usernames = [user['username'] for user in all_users if dashboard_uname_rx.match(user['username'])]

        usage_counts, indicators_count = self.get_dashboard_usage_counts(start_date, end_date, usernames)

        self.get_request_data(all_users, usage_counts, indicators_count)
        print(f'Request data written to file {REQUEST_DATA_CACHE}')

    def convert_rows_to_list(self, results_queryset):
        """
        :param results_queryset: AwcLocation values queryset
        :return: location matrix similar to a dataframe and locations ids of all the locations below the given and
         location id to name mapping dict
         location
        """
        location_matrix = []
        location_id_name_mapping = defaultdict(str)

        for result in results_queryset:
            row_data = [result['state_id'], result['state_name'], result['district_id'],
                        result['district_name'], result['block_id'], result['block_name']]
            location_matrix.append(row_data)
            for location_type in self.location_types:
                if result[location_type] not in location_id_name_mapping.keys():
                    location_id_name_mapping[result[location_type]] =\
                        result[self.get_location_name_string_from_location_id(location_type)]
        return location_matrix

    def get_dashboard_usage_counts(self, start_date, end_date, usernames):
        print(f'Compiling usage counts for {len(usernames)} users')
        user_counts = defaultdict(int)
        user_indicators = defaultdict(list)
        for chunk in with_progress_bar(chunked(usernames, 50), prefix='\tProcessing'):
            query = (
                    ICDSAuditEntryRecord.objects.filter(url='/a/icds-dashboard-qa/cas_export',
                                                        username__in=chunk, time_of_use__gte=start_date,
                                                        time_of_use__lte=end_date)
                    .annotate(indicator=KeyTextTransform('indicator', 'post_data')).values('indicator',
                                                                                           'username')
                    .annotate(count=Count('indicator')).order_by('username', 'indicator'))
            for record in query:
                user_counts[record['username']] += record['count']
                user_indicators[record['username']].append(record['count'])

        return user_counts, user_indicators

    def get_role_from_username(self, username):
        for key, value in self.roles.items():
            if key.lower() in username:
                return value
        return 'N/A'

    def get_location_name_string_from_location_id(self, location_id):
        return location_id.replace('_id', 'name')

    def get_request_data(self, users, user_indicators, user_counts):
        request_data = []
        location_type_filter = {
            'aggregation_level': 5
        }
        for test_location in self.location_test_fields:
            location_type_filter[test_location] = 0
        all_awc_locations = AwcLocation.objects.filter(**location_type_filter).values(*self.required_fields)

        location_matrix, location_mapping = self.convert_rows_to_list(all_awc_locations)

        print(f'Compiling request data for {len(users)} users')
        for chunk in with_progress_bar(chunked(users, 50), prefix='\tProcessing'):
            for user in chunk:
                indicator_count = user_indicators[user['username']]
                user_sql_location_ids = user['assigned_location_ids']
                if isinstance(user_sql_location_ids, str):
                    user_sql_location_ids = [user_sql_location_ids]

                for user_sql_location in user_sql_location_ids:
                    if user_sql_location not in location_mapping:
                        continue
                    location_type_id = self.sql_locations[user_sql_location]
                    column_index = self.location_types.index(location_type_id)
                    user_location_row = None
                    # iterating and getting the db row from matrix
                    for row in location_matrix:
                        if row[2 * column_index] == user_sql_location:
                            user_location_row = copy.deepcopy(row)
                            break
                    user_location_type = self.get_location_type_string_from_location_id(location_type_id)

                    if user_location_row is not None:
                        if user_location_type == 'state':
                            user_location_row[3] = 'All'
                            user_location_row[5] = 'All'
                        if user_location_type == 'district':
                            user_location_row[5] = 'All'

                        excel = [0, user_location_row[1], user_location_row[3],
                                 user_location_row[5], user['username'].split('@')[0], user_location_type,
                                 self.get_role_from_username(user['username']), user_counts[user['username']]]
                        excel.extend(indicator_count)
                        request_data.append(excel)
        _write_to_file(REQUEST_DATA_CACHE, request_data)


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
