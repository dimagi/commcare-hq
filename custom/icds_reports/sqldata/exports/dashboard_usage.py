
import datetime
import re
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from corehq.apps.es import UserES
from custom.icds_reports.models import AwcLocation
from custom.icds_reports.models.aggregate import DashboardUserActivityReport
from custom.icds_reports.utils import india_now


class DashBoardUsage:

    title = 'Dashboard usage'
    required_fields = ['state_id', 'state_name', 'district_id', 'district_name', 'block_id', 'block_name']
    location_types = ['state_id', 'district_id', 'block_id']
    location_test_fields = ['state_is_test', 'district_is_test', 'block_is_test', 'supervisor_is_test',
                            'awc_is_test']
    user_levels = [location_type.replace('_id', '') for location_type in location_types]

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
        self.location_id_name_dict = defaultdict(str)
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

    def populate_location_id_vs_name_mapping(self, results_queryset, main_location_type=None):
        """
        :param results_queryset: AwcLocation values queryset
        :param main_location_type: parent location type to fetch only locations below that level
        :return: dict with location id and value mapping and locations ids of all the locations below the given
         location
        """
        location_ids = []
        for result in results_queryset:
            for sub_location in self.location_types:
                if result[sub_location] not in location_ids:
                    location_ids.append(result[sub_location])
                    # adding location id and name to the dict
                    self.location_id_name_dict[result[sub_location]] = result[
                        self.get_location_type_string_from_location_id(sub_location) + '_name']
        return location_ids

    def get_location_id_string_from_location_type(self, location_type):
        return location_type + '_id'

    def get_location_type_string_from_location_id(self, location_id):
        return location_id.replace('_id', '')

    def check_if_date_in_last_week(self, date):
        if date is None:
            return 'N/A', False
        date_formatted = datetime.datetime.strftime(date, "%d/%m/%Y, %I:%M %p")
        now = datetime.datetime.now()
        return date_formatted, (now - date).days < 7

    def get_location_name_from_id(self, location_id):
        return self.location_id_name_dict[location_id]

    def get_data_for_usgae_report(self, date, filters):
        return list(DashboardUserActivityReport.objects.filter(date=date, **filters))

    def get_excel_data(self):
        excel_rows = []
        filters = [['Generated at', india_now()]]

        headers = ['Sr.No', 'State/UT Name', 'District Name', 'Block Name', 'Username', 'Level', 'Role',
                   'Launched?', 'Last Login  Activity ', 'Activity in the last 7 days?']
        serial_count = 0
        logged_in_user_locations = list(self.user.get_sql_locations(self.domain))
        if not logged_in_user_locations:
            self.national_user = True

        loop_counter = 0
        # Need to fetch all users for a national user
        while (self.national_user and loop_counter < 1) or len(logged_in_user_locations) > loop_counter:
            location_type_filter = {
                'aggregation_level': 5
            }
            if not self.national_user:
                user_location = logged_in_user_locations[loop_counter]
                user_location_type_name = \
                    self.get_location_id_string_from_location_type(user_location.location_type_name)
                location_type_filter[user_location_type_name] = user_location.get_id
            else:
                user_location_type_name = None
            for test_location in self.location_test_fields:
                location_type_filter[test_location] = 0

            all_awc_locations = AwcLocation.objects.filter(**location_type_filter).values(*self.required_fields)

            location_ids = self.populate_location_id_vs_name_mapping(all_awc_locations, user_location_type_name)

            users = self.get_users_by_location(location_ids)

            dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')

            usernames = [user['username'] for user in users if dashboard_uname_rx.match(user['username'])]

            date = datetime.datetime.now().date()
            usage_data = None
            dashboard_filters = {'username__in': usernames}
            # keep the record in searched - current - month
            while usage_data is None:
                usage_data = self.get_data_for_usgae_report(date, dashboard_filters)
                date -= relativedelta(days=1)

            for record in usage_data:
                last_activity, activity_in_last_week = self.check_if_date_in_last_week(record.last_activity)
                district_name = self.get_location_name_from_id(record.district_id)
                block_name = self.get_location_name_from_id(record.block_id)
                if record.user_level == 1:
                    district_name = ''
                    block_name = ''
                elif record.user_level == 2:
                    block_name = ''
                excel = [serial_count, self.get_location_name_from_id(record.state_id),
                         district_name, block_name, record.username.split('@')[0],
                         self.user_levels[record.user_level-1],
                         self.get_role_from_username(record.username),
                         self.convert_boolean_to_string(record.location_launched),
                         last_activity,
                         self.convert_boolean_to_string(activity_in_last_week)]
                excel_rows.append(excel)
            loop_counter += 1
        excel_rows = sorted(excel_rows, key=lambda x: (x[1], x[2], x[3]))
        # appending serial numbers
        for i in range(len(excel_rows)):
            serial_count += 1
            excel_rows[i][0] = serial_count
        excel_rows.insert(0, headers)
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
