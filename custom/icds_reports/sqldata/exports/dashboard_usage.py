
import datetime
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import INDIA_TIMEZONE
from custom.icds_reports.models import AwcLocation
from custom.icds_reports.models.aggregate import DashboardUserActivityReport
from custom.icds_reports.utils import india_now
from django.utils.functional import cached_property


class DashBoardUsage:

    title = 'Dashboard Activity Report'
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
        '.sbp': 'Swasth Bharat Prerak'
    }

    def __init__(self, couch_user, domain):
        self.user = couch_user
        self.domain = domain
        self.location_id_name_dict = defaultdict(str)

    def get_role_from_username(self, username):
        for key, value in self.roles.items():
            if key.lower() in username:
                return value
        return 'N/A'

    def convert_boolean_to_string(self, value):
        return 'yes' if value else 'no'

    def populate_location_id_vs_name_mapping(self, results_queryset, main_location_type=None):
        """
        :param results_queryset: AwcLocation values queryset
        :param main_location_type: parent location type to fetch only locations below that level
        """
        location_ids = []
        for result in results_queryset:
            for sub_location in self.location_types:
                if result[sub_location] not in location_ids:
                    location_ids.append(result[sub_location])
                    # adding location id and name to the dict
                    self.location_id_name_dict[result[sub_location]] = result[
                        self.get_location_type_string_from_location_id(sub_location) + '_name']

    def get_location_id_string_from_location_type(self, location_type):
        """
        Appends location _id the location
        :param location_type:
        :return:
        """
        return location_type + '_id'

    def get_location_type_string_from_location_id(self, location_id):
        return location_id.replace('_id', '')

    def check_if_date_in_last_week(self, date):
        """
        checks if the date is in last 7 days excluding today
        :param date: user last activity date
        :return: Returns if the user has an activity in dashboard in last 7 days
        """
        if date is None:
            return 'N/A', False
        date = self.convert_utc_to_ist(date)
        date_formatted = datetime.datetime.strftime(date, "%d/%m/%Y, %I:%M %p")
        now = datetime.datetime.now(INDIA_TIMEZONE)
        seven_days_before_date = (now - relativedelta(days=7)).date()
        return date_formatted, seven_days_before_date <= date.date() < now.date()

    def convert_utc_to_ist(self, utc_date):
        """
        converts utc date to ist date
        :param utc_date:
        :return: ist date
        """
        return utc_date.astimezone(INDIA_TIMEZONE)

    def get_location_name_from_id(self, location_id):
        """
        :param location_id: location_id
        :return: Returns the name of the location
        """
        return self.location_id_name_dict[location_id]

    def get_data_for_usage_report(self, date, filters):
        """
        :param date: Date for which the report is needed
        :param filters: Filter for the DashboardUserActivityReport
        :return:Returns a list of activity report records based on the filters
        """
        return list(DashboardUserActivityReport.objects.filter(date=date, **filters))

    @cached_property
    def is_national_user(self):
        """
        :return: Returns if the users has access to all locations or not
        """
        logged_in_user_locations = list(self.user.get_sql_locations(self.domain))
        if not logged_in_user_locations or self.user.has_permission(self.domain, 'access_all_locations'):
            return True
        return False

    def get_excel_data(self):
        excel_rows = []
        filters = [['Generated at', india_now()]]

        headers = ['Sr.No', 'State/UT Name', 'District Name', 'Block Name', 'Username', 'Level', 'Role',
                   'Launched?', 'Last Activity ', 'Activity in the last 7 days?']
        serial_count = 0

        location_type_filter = {
            'aggregation_level': 3
        }
        if not self.is_national_user:
            user_location = self.user.get_sql_location(self.domain)
            user_loc_id_key = \
                self.get_location_id_string_from_location_type(user_location.location_type_name)
            location_type_filter[user_loc_id_key] = user_location.get_id
        else:
            user_loc_id_key = None
        for test_location in self.location_test_fields:
            location_type_filter[test_location] = 0

        all_awc_locations = AwcLocation.objects.filter(**location_type_filter).values(*self.required_fields)

        self.populate_location_id_vs_name_mapping(all_awc_locations, user_loc_id_key)

        date = datetime.datetime.now()
        usage_data = []

        dashboard_filters = {}

        if not self.is_national_user:
            # retrieving the user_level from logged in user location type
            user_level = self.user_levels.index(user_loc_id_key.replace('_id', '')) + 1
            dashboard_filters['user_level__gt'] = user_level

            dashboard_filters[user_loc_id_key] = user_location.get_id

        # keep the record in searched - current - month
        while not usage_data:
            usage_data = self.get_data_for_usage_report(date, dashboard_filters)
            date -= relativedelta(days=1)

        for record in usage_data:
            user_activity = record.last_activity if record.location_launched else None
            last_activity, activity_in_last_week = self.check_if_date_in_last_week(user_activity)

            state_name = self.get_location_name_from_id(record.state_id)
            district_name = self.get_location_name_from_id(record.district_id)
            block_name = self.get_location_name_from_id(record.block_id)

            excel = [serial_count, state_name,
                     district_name, block_name, record.username.split('@')[0],
                     self.user_levels[record.user_level - 1],
                     self.get_role_from_username(record.username),
                     self.convert_boolean_to_string(record.location_launched),
                     last_activity,
                     self.convert_boolean_to_string(activity_in_last_week)]
            excel_rows.append(excel)

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
