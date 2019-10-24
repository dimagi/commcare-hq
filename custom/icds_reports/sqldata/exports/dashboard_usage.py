import datetime
import re
from collections import defaultdict

import dateutil
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import Count

from corehq.apps.es import UserES
from custom.icds_reports.models import AwcLocation, ICDSAuditEntryRecord, AggAwc
from custom.icds_reports.utils import india_now


class DashBoardUsage:

    title = 'Dashboard usage'
    required_fields = ['state_id', 'state_name', 'district_id', 'district_name', 'block_id', 'block_name']
    location_types = ['state_id', 'district_id', 'block_id']
    agg_required_fields = ['state_id', 'district_id', 'block_id', 'is_launched']

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

    def __init__(self, couch_user, domain):
        self.user = couch_user
        self.domain = domain
        self.agg_list = None
        self.sql_locations = None
        self.national_user = False

    def get_role_from_username(self, username):
        for key, value in self.roles.items():
            if key.lower() in username:
                return value
        return 'N/A'

    def convert_boolean_to_string(self, value):
        return 'yes' if value else 'no'

    def get_users_by_location(self, user_supported_locations):
        if not self.national_user:
            user_query = UserES().mobile_users().domain(self.domain).location(
                user_supported_locations
            ).fields(['username', 'assigned_location_ids', 'last_login'])
        else:
            user_query = UserES().mobile_users().domain(self.domain
                                                        ).fields(['username',
                                                                  'assigned_location_ids',
                                                                  'last_login'])
        return [u for u in user_query.run().hits]

    def get_names_from_ids(self, location_id):
        return location_id.split('_')[0] + '_name'

    def convert_rs_to_matrix(self, results_queryset, main_location_type=None):
        """

        :param results_queryset: AwcLocation values queryset
        :param main_location_type: parent location type to fetch only locations below that level
        :return: location matrix similar to a dataframe and locations ids of all the locations below the given
         location
        """
        location_matrix = []
        location_ids = []
        if main_location_type is not None:
            sub_location_types = self.location_types[self.location_types.index(main_location_type) + 1:]
        else:
            sub_location_types = self.location_types

        for result in results_queryset:
            row_data = [result['state_id'], result['district_id'], result['block_id'], result['supervisor_id'],
                        result['doc_id']]
            location_matrix.append(row_data)
            # adding only descendants to the main location
            for sub_location in sub_location_types:
                if result[sub_location] not in location_ids:
                    location_ids.append(result[sub_location])
        return location_matrix, location_ids

    def get_location_id_string_from_location_type(self, location_type):
        return location_type + '_id'

    def get_location_type_string_from_location_id(self, location_id):
        return location_id.replace('_id', '')

    def check_if_date_in_last_week(self, date):
        if date is None:
            return False
        d = dateutil.parser.parse(date).strftime("%Y-%m-%d")
        d = datetime.datetime.strptime(d, "%Y-%m-%d")
        now = datetime.datetime.now()
        return (now - d).days < 7

    def prepare_is_launched_agg_list(self, location_type=None, location_id=None):
        """
        populates the location_id vs is_launched status and location_id vs location_type mappings for the
         descendants of given location
        :param location_type:
        :param location_id:
        :return: None
        """
        filter_dict = {'aggregation_level': 5,
                       'month': datetime.date.today().replace(day=1)}
        if location_type is not None:
            location_type = self.get_location_id_string_from_location_type(location_type)
            sub_location_types = self.agg_required_fields[self.location_types.index(location_type) + 1:]
            filter_dict[location_type] = location_id
        else:
            sub_location_types = self.agg_required_fields

        aggregate_records = AggAwc.objects.filter(**filter_dict).values(*sub_location_types)

        aggregate_records_dict = defaultdict(str)
        location_type_id_mapping = defaultdict(str)

        for aggregate_record in aggregate_records:
            for sub_location_type in sub_location_types:
                if sub_location_type != 'is_launched':
                    if aggregate_record[sub_location_type] not in aggregate_records_dict or not\
                            aggregate_records_dict[aggregate_record[sub_location_type]]:
                        aggregate_records_dict[aggregate_record[sub_location_type]] =\
                            aggregate_record['is_launched']
                    if aggregate_record[sub_location_type] not in location_type_id_mapping:
                        location_type_id_mapping[aggregate_record[sub_location_type]] = sub_location_type

        self.agg_list = aggregate_records_dict
        self.sql_locations = location_type_id_mapping

    def get_excel_data(self):
        excel_rows = []
        filters = [['Generated at', india_now()]]
        headers = ['Sr.No', 'State/UT Name', 'District Name', 'Block Name', 'Username', 'Level', 'Role',
                   'Launched?', 'Last Login', 'Logged in the last week?', 'Total', 'Child', 'Pregnant Women',
                   'Demographics', 'System Usage', 'AWC infrastructure', 'Child Growth Monitoring List',
                   'ICDS - CAS Monthly Register', 'AWW Performance Report', 'LS Performance Report',
                   'Take Home Ration']
        excel_rows.append(headers)
        serial_count = 0
        logged_in_user_locations = list(self.user.get_sql_locations(self.domain))
        if not logged_in_user_locations:
            self.national_user = True

        loop_counter = 0
        # Need to fetch all users for a national user
        while (self.national_user and loop_counter < 1) or len(logged_in_user_locations) > loop_counter:
            user_location = logged_in_user_locations[loop_counter]
            # getting the location types to retrieve for this user location

            location_type_filter = {
                'aggregation_level': 5
            }
            if not self.national_user:
                location_type_filter[self.get_location_id_string_from_location_type(
                    user_location.location_type_name)]: user_location.get_id

            all_awc_locations = AwcLocation.objects.filter(**location_type_filter).values(*self.required_fields)
            # converting the result set to matrix to fetch ancestors for a given location
            location_matrix, location_ids =\
                self.convert_rs_to_matrix(all_awc_locations, self.get_location_id_string_from_location_type(
                    user_location.location_type_name))

            users = self.get_users_by_location(location_ids)

            dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')

            usernames = [user['username'] for user in users if dashboard_uname_rx.match(user['username'])]

            records = list(ICDSAuditEntryRecord.objects.filter(url='/a/icds-dashboard-qa/cas_export',
                                                               username__in=usernames)
                           .annotate(indicator=KeyTextTransform('indicator', 'post_data')).values('indicator',
                                                                                                  'username')
                           .annotate(count=Count('indicator')).order_by('username', 'indicator'))

            if self.national_user:
                self.prepare_is_launched_agg_list()
            else:
                self.prepare_is_launched_agg_list(user_location.location_type_name, user_location.get_id)

            user_counts = defaultdict(int)
            user_indicators = defaultdict(list)
            for record in records:
                user_counts[record['username']] += record['count']
                user_indicators[record['username']].append(record['count'])
            # accumulating the indicator counts
            for user in users:
                indicator_count = user_indicators[user['username']]
                user_sql_location_ids = user['assigned_location_ids']
                if isinstance(user_sql_location_ids, str):
                    user_sql_location_ids = [user_sql_location_ids]

                for user_sql_location in user_sql_location_ids:
                    # getting the location type to look up in matrix
                    location_type_id = self.sql_locations[user_sql_location]
                    column_index = self.location_types.index(location_type_id)
                    user_location_row = None
                    # iterating and getting the db row from matrix
                    for row in location_matrix:
                        if row[column_index] == user_sql_location:
                            user_location_row = row
                            break
                    user_location_type = self.get_location_type_string_from_location_id(location_type_id)

                    if user_location_row is not None:
                        if user_location_type == 'state':
                            user_location_row[1] = 'All'
                            user_location_row[2] = 'All'
                        if user_location_type == 'district':
                            user_location_row[2] == 'All'
                        serial_count += 1

                        excel = [serial_count, user_location_row[0], user_location_row[1],
                                 user_location_row[2], user['username'], user_location_type,
                                 self.get_role_from_username(user['username']),
                                 self.convert_boolean_to_string(self.agg_list[user_sql_location]),
                                 user['last_login'],
                                 self.convert_boolean_to_string(self.check_if_date_in_last_week(
                                     user['last_login'])), user_counts[user['username']]]
                        excel.extend(indicator_count)
                        excel_rows.append(excel)
            loop_counter += 1

        return [
            [
                self.title,
                excel_rows
            ],
            [
                'Export Info',
                filters
            ]
        ]
