import datetime

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import Count

from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models import AwcLocation, ICDSAuditEntryRecord, AggAwc
from custom.icds_reports.utils import india_now


class DashBoardUsage:

    title = 'Dashboard usage'
    required_fields = ['state_id', 'state_name', 'district_id', 'district_name', 'block_id', 'block_name',
                       'supervisor_id', 'supervisor_name', 'doc_id', 'awc_name']
    location_types = ['state_id', 'district_id', 'block_id', 'supervisor_id', 'doc_id']
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

    def get_role_from_username(self, username):
        for key, value in self.roles.items():
            if key.lower() in username:
                return value

    def convert_boolean_to_string(self, value):
        return 'yes' if value else 'no'

    def get_users_by_location(self, user_supported_locations):
        user_query = UserES().mobile_users().domain(self.domain).location(
            user_supported_locations
        ).fields(['username', 'assigned_location_ids', 'last_login'])
        return [u for u in user_query.run().hits]

    def get_names_from_ids(self, location_id):
        if location_id == 'doc_id':
            return 'awc_name'
        else:
            return location_id.split('_')[0] + '_name'

    def convert_rs_to_matrix(self, results_queryset, main_location_type):
        """

        :param results_queryset: AwcLocation values queryset
        :param main_location_type: parent location type to fetch only locations below that level
        :return: location matrix similar to a dataframe and locations ids of all the locations below the given
         location
        """
        location_matrix = []
        location_ids = []
        for result in results_queryset:
            row_data = [result['state_id'], result['district_id'], result['block_id'], result['supervisor_id'],
                        result['doc_id']]
            location_matrix.append(row_data)
        # adding only descendants to the main location
        sub_location_types = self.location_types[self.location_types.index(main_location_type) + 1:]
        for sub_location in sub_location_types:
            if result[sub_location] not in location_ids:
                location_ids.append(result[sub_location])
        return location_matrix, location_ids

    def get_location_id_string_from_location_type(self, location_type):
        if location_type == 'awc':
            location_type = 'doc_id'
        else:
            location_type = location_type + '_id'
        return location_type

    def check_if_date_in_last_week(self, date):
        if date is None:
            return False
        d = datetime.datetime.strptime(date, "%Y-%m-%d")
        now = datetime.datetime.now()
        return (d - now).days < 7

    def is_launched_from_location_id(self, location_type, location_id):
        filter_dict = {location_type + '_id': location_id, 'is_launched': 'yes'}
        return AggAwc.objects.filter(**filter_dict).exists()

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
        from custom.icds_reports.tests.test1 import get_awc_locations
        for user_location in self.user.get_sql_locations(self.domain):
            # getting the location types to retrieve for this user location
            location_type_filter = {
                self.get_location_id_string_from_location_type(user_location.location_type_name):
                    user_location.get_id}
            all_awc_locations = AwcLocation.objects.filter(**location_type_filter).values(*self.required_fields)
            # converting the result set to matrix to fetch ancestors for a given location
            location_matrix, location_ids =\
                self.convert_rs_to_matrix(all_awc_locations, self.get_location_id_string_from_location_type(
                    user_location.location_type_name))
            users = self.get_users_by_location(location_ids)
            records = list(ICDSAuditEntryRecord.objects.filter(url='/a/icds-dashboard-qa/cas_export')
                           .annotate(indicator=KeyTextTransform('indicator', 'post_data')).values('indicator',
                                                                                                  'username')
                           .annotate(count=Count('indicator')).order_by('username', 'indicator'))
            # accumulating the indicator counts
            for user in users:
                indicator_count = []
                total_indicators = 0
                for record in records:
                    if record['username'] == user['username']:
                        total_indicators += record['count']
                        indicator_count.append(record['count'])

                user_sql_location_ids = user['assigned_location_ids']
                filter_dict = {}
                if isinstance(user_sql_location_ids, str):
                    filter_dict['location_id'] = user_sql_location_ids
                else:
                    filter_dict['location_id__in'] = user_sql_location_ids
                user_sql_locations = SQLLocation.objects.filter(**filter_dict) \
                    .values('location_id', 'location_type__name')
                for user_sql_location in user_sql_locations:
                    # getting the location type to look up in matrix
                    location_type_id = self.get_location_id_string_from_location_type(
                        user_sql_location['location_type__name'])
                    column_index = self.location_types.index(location_type_id)
                    user_location_row = None
                    # iterating and getting the db row from matrix
                    for row in location_matrix:
                        if row[column_index] == user_sql_location['location_id']:
                            user_location_row = row
                            break
                    if user_location_row is not None:
                        serial_count += 1
                        excel = [serial_count, user_location_row[0], user_location_row[1],
                                 user_location_row[2], user['username'], user_sql_location['location_type__name'],
                                 self.get_role_from_username(user['username']),
                                 self.convert_boolean_to_string(self.is_launched_from_location_id(
                                     user_sql_location['location_type__name'], user_sql_location['location_id'])),
                                 user['last_login'],
                                 self.convert_boolean_to_string(self.check_if_date_in_last_week(
                                     user['last_login'])), total_indicators]
                        excel.extend(indicator_count)
                        excel_rows.append(excel)
                        print(excel)
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
