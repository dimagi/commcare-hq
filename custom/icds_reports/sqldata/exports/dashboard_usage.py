import datetime
from math import floor

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import Count

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models import AwcLocation, ICDSAuditEntryRecord
from custom.icds_reports.utils import india_now


class DashBoardUsage:

    title = 'Dashboard usage'
    location_types = ['state_id', 'state_name', 'district_id', 'district_name', 'block_id', 'block_name',
                      'supervisor_id', 'supervisor_name', 'doc_id', 'awc_name']

    def __init__(self, couch_user):
        self.user = couch_user

    def get_names_from_ids(self, location_id):
        if location_id == 'doc_id':
            return 'awc_name'
        else:
            return location_id.split('_')[0] + '_name'

    def convert_rs_to_matrix(self, results_queryset):
        location_matrix = []
        location_ids = []
        for result in results_queryset:
            row_data = [result['state_id'], result['district_id'], result['supervisor_id'], result['block_id'],
                        result['doc_id']]
            location_matrix.append(row_data)
            location_ids.extend(row_data)
        return location_matrix, location_ids

    def get_location_type_from_user_location(self, location_type):
        if location_type == 'awc':
            location_type = 'doc_id'
        else:
            location_type = location_type + '_id'
        return location_type

    def check_if_date_in_last_week(self, date):
        d = datetime.datetime.strptime(date, "%Y-%m-%d")
        now = datetime.datetime.now()
        return (d - now).days < 7

    def get_excel_data(self):
        excel_rows = []
        headers = ['Sr.No', 'State/UT Name', 'District Name', 'Block Name', 'Username', 'Level', 'Last Login ',
                   'Logged in the last week?', 'Total', 'Child', 'Pregnant Women', 'Demographics',
                   'System Usage', 'AWC infrastructure', 'Child Growth Monitoring List', 'ICDS - CAS Monthly Register',
                   'AWW Performance Report', 'LS Performance Report', 'Take Home Ration']
        excel_rows.append(headers)
        serial_count = 0
        for user_location in self.user.get_sql_locations():
            # getting the location types to retrieve for this user location
            location_type_filter = {
                self.get_location_type_from_user_location(user_location.location_type_name): user_location.get_id}
            all_awc_locations = AwcLocation.objects.filter(**location_type_filter).values(*self.location_types)
            # converting the result set to matrix to fetch ancestors for a given location id
            location_matrix, location_ids = self.convert_rs_to_matrix(all_awc_locations)
            users = self.get_users_by_location(location_ids)
            records = list(ICDSAuditEntryRecord.objects.filter(url='/a/icds-dashboard-qa/cas_export')
                           .annotate(indicator=KeyTextTransform('indicator', 'post_data')).values('indicator',
                                                                                                  'username')
                           .annotate(total=Count('indicator')).order_by('username', 'indicator'))
            # accumulating the indicator counts
            for user in users:
                indicator_count = []
                total_indicators = 0
                for record in records:
                    if record['username'] == user.username:
                        total_indicators += record['count']
                        indicator_count.append(record['count'])

                user_sql_location_ids = user.assigned_location_ids
                user_sql_locations = SQLLocation.objects.filter(location_id__in=user_sql_location_ids) \
                    .values('location_id', 'location_type__name')
                for user_sql_location in user_sql_locations:
                    # getting the location type to look up in matrix
                    location_type = self.get_location_type_from_user_location(user_sql_location['location_type__name'])
                    column_index = floor(self.location_types.index(location_type) / 2)
                    user_location_row = None
                    # iterating and getting the db row
                    for row in location_matrix:
                        if row[column_index] == user_sql_location['location_id']:
                            user_location_row = row
                            break
                    serial_count += 1
                    excel = [serial_count, user_location_row[0], user_location_row[1],
                             user_location_row[2], user.username, user_sql_location['location_type__name'],
                             user.last_logged_in, self.check_if_date_in_last_week(user.last_logged_in),
                             total_indicators]
                    excel.extend(indicator_count)
                    excel_rows.append(excel)
                    filters = [['Generated at', india_now()]]
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
