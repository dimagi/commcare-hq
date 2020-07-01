import csv

from corehq.apps.es.forms import FormES
from datetime import datetime
from corehq.apps.users.models import CommCareUser
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


def _run_custom_sql_script(command, day=None):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return

    cursor = connections[db_alias].cursor()
    cursor.execute(command, [day])

    return cursor.fetchall()


def state_details():
    query = """
        SELECT
            awc.state_name as state_name,
            awc.supervisor_name as supervisor_name,
            l.supervisor_id as supervisor_id,
            awc.supervisor_site_code as supervisor_site_code,
            CASE WHEN l.num_supervisor_launched>0 THEN 'Launched'
            ELSE 'UnLaunched' END as supervisor_launched_status
            FROM "agg_ls" l
            LEFT JOIN "awc_location_local" awc
                ON (
                awc.supervisor_id = l.supervisor_id
                AND l.aggregation_level=awc.aggregation_level )
            WHERE l.month='2020-06-01' AND l.aggregation_level=4 AND awc.supervisor_is_test<>1 AND awc.state_is_test<>1
        """
    return _run_custom_sql_script(query)


class Command(BaseCommand):
    help = "Run Custom Data Pull"

    def get_users(self, users):
        users = list(set(users))
        user_location_details = {}
        for user in users:
            t = CommCareUser.get_by_user_id(user)
            user_location_details.update({
                user: t.location_id
            })
        print("================================User details fetched=========\n")
        print(len(user_location_details))
        print("===============================================================")
        return user_location_details

    def handle(self, **options):

        query = FormES().domain('icds-cas').xmlns('http://openrosa.org/formdesigner/327e11f3c04dfc0a7fea9ee57d7bb7be83475309').submitted(gte=datetime(2020,6,1), lt=datetime(2020,7,1))
        forms_list = query.run().hits

        users = []
        for form in forms_list:
            users.append(form['form']['case']['@user_id'])
        user_location_details = self.get_users(users)
        location_details = state_details()
        headers = ['state_name', 'supervisor_site_code', 'launched_status', 'visit_type', 'beneficiary_type', 'visit_count']
        data_rows = [headers]
        home_visit = ["due_for_delivery", "just_delivered", "six_to_eight_months","underweight_child", "recent_registered_preg", "ben_death"]
        vhnd = ["pregnant_woman", "received_dpt1", "received_dpt3", "received_measles"]
        fast_data_rows = {}
        for location in location_details:
            for visit in home_visit:
                row = [
                    location[0],
                    location[3],
                    location[4],
                    "home_visit",
                    visit,
                    0
                ]
                fast_data_rows.update({f"{location[2]}_home_visit_{visit}": row})
            for visit in vhnd:
                row = [
                    location[0],
                    location[3],
                    location[4],
                    "vhnd_day",
                    visit,
                    0
                ]
                fast_data_rows.update({f"{location[2]}_vhnd_day_{visit}": row})
        count = 0
        supervisor_ids = [location[2] for location in location_details]
        for form in forms_list:
            supervisor_id = user_location_details[form['form']['case']['@user_id']]
            m_type = form['form']['meeting_type']
            if m_type == 'vhnd_day':
                visit = form['form']['beneficiary_type_for_visit_vhnd']
            else:
                visit = form['form']['beneficiary_type_for_visit']
            if supervisor_id in supervisor_ids:
                fast_data_rows[f"{supervisor_id}_{m_type}_{visit}"][5] = fast_data_rows[f"{supervisor_id}_{m_type}_{visit}"][5] + 1
            if count % 1000 == 0:
                print(f"{count} forms processed ======\n")
            count = count + 1
        for key, value in fast_data_rows.items():
            data_rows = data_rows + [value]
        fout = open('/home/cchq/LS_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(data_rows)


        print("=========starting the VHNSD data pull=====\n")
        headers = ['state_name', 'supervisor_site_code', 'launched_status',
                   'total_vhnsd_visit_count', 'unique_awc_visited']
        data_rows = [headers]
        fast_rows = {}
        for location in location_details:
            row = [
                location[0],
                location[3],
                location[4],
                0,
                set()
            ]
            fast_rows.update({location[2]: row})
        query = FormES().domain('icds-cas').xmlns(
            'http://openrosa.org/formdesigner/b8273b657bb097eb6ba822663b7191ff6bc276ff').submitted(
            gte=datetime(2020, 6, 1), lt=datetime(2020, 7, 1))
        forms_list = query.run().hits
        users = []
        for form in forms_list:
            users.append(form['form']['case']['@user_id'])
        user_location_details = self.get_users(users)
        count = 0
        supervisor_ids = [location[2] for location in location_details]
        for form in forms_list:
            supervisor_id = user_location_details[form['form']['case']['@user_id']]
            awc_selected_name = form['form']['awc_selected_name']
            if supervisor_id in supervisor_ids:
                fast_rows[supervisor_id][3] = fast_rows[supervisor_id][3] + 1
                fast_rows[supervisor_id][4].add(awc_selected_name)
            if count % 1000 == 0:
                print(f"{count} forms processed ======\n")
            count = count + 1

        for key, value in fast_rows.items():
            value[4] = len(value[4])
            data_rows = data_rows + [value]
        fout = open('/home/cchq/LS_data_vhnsd.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(data_rows)





