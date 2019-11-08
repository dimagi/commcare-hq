from custom.icds_reports.models.util import ICDSAuditEntryRecord
from custom.icds_reports.models.aggregate import  AggAwc
import re
from datetime import date
from corehq.apps.users.models import CommCareUser
import csv




user_objects = {}
dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')


date_setp = [(date(2019,9,2),date(2019,9,8)),(date(2019,9,9),date(2019,9,15)),(date(2019,9,16),date(2019,9,22)),(date(2019,9,23),date(2019,9,29)),(date(2019,9,30),date(2019,9,30))]
dates_oct = [(date(2019,10,1), date(2019,10,6)),(date(2019,10,7),date(2019,10,13)),(date(2019,10,14),date(2019,10,20)),(date(2019,10,21),date(2019,10,27)),(date(2019,10,28),date(2019,11,3))]


def get_user_obj(username):
    if username in user_objects:
        return user_objects[username]
    else:
        return CommCareUser.get_by_username(username)


def get_launched_locations(month):

    x = AggAwc.objects.filter(month=month,aggregation_level=3,num_launched_awcs__gt=0).values('state_id','district_id','block_id')

    launched_states = []
    launched_districts = []
    launched_blocks = []

    for record in x:
        launched_states.append(record['state_id'])
        launched_districts.append(record['district_id'])
        launched_blocks.append(record['block_id'])

    return {
            'states':launched_states,
            'districts':launched_districts,
            'blocks':launched_blocks
            }


def get_data(dates, month):
    launched_locations = get_launched_locations(month)

    for date in dates:
        user_names = ICDSAuditEntryRecord.objects.filter(time_of_use__gte=date[0],time_of_use__lte=date[1]).values_list('username', flat=True)

        rows = []
        logged_in_dashboard_users = {u for u in user_names if dashboard_uname_rx.match(u)}

        for username in logged_in_dashboard_users:
            user = get_user_obj(username)
            loc = user.sql_location
            loc_name = loc.name.encode('ascii', 'replace').decode() if loc else ''
            is_launched = 'no'
            if loc.location_type.name =='state'  and loc.location_id  in launched_locations['states']:
                is_launched='yes'
            if loc.location_type.name =='district' and loc.location_id not in launched_locations['states']:
                is_launched = 'yes'
            if loc.location_type.name =='block' and loc.location_id not in launched_locations['states']:
                is_launched = 'yes'
            if loc.location_type.name =='state':
                state_name = loc_name
                district_name = 'All'
                block_name = 'All'
            if loc.location_type.name == 'district':
                state = loc.get_ancestor_of_type('state') if loc else None
                state_name = state.name.encode('ascii', 'replace').decode() if state else ''
                district_name = loc_name
                block_name = 'All'
            if loc.location_type.name == 'block':
                state = loc.get_ancestor_of_type('state') if loc else None
                state_name = state.name.encode('ascii', 'replace').decode() if state else ''
                district = loc.get_ancestor_of_type('district') if loc else None
                district_name = district.name.encode('ascii', 'replace').decode() if state else ''
                block_name = loc_name
            rows.append('"{}","{}","{}","{}","{}","{}"'.format(username, loc.location_type.name, state_name,district_name,block_name,is_launched))

        with csv.writer(open('/home/cchq/usage_date_from_{}_to_{}.csv'.format(date[0],date[1]),'wb')) as writer:
            writer.writerows(rows)


get_data(date_setp,'2019-09-01')
get_data(dates_oct, '2019-10-01')
