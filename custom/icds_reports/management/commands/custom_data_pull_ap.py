import csv
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import connections, transaction

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias

query_to_fetch_awcs = """
    SELECT doc_id, awc_name, awc_site_code, supervisor_name, block_name, district_name
    FROM awc_location WHERE aggregation_level=5 AND state_id='f98e91aa003accb7b849a0f18ebd7039'
"""

#                                                               QUERY PLAN
# ---------------------------------------------------------------------------------------------------------------------------------------
#  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
#    Task Count: 1
#    Tasks Shown: All
#    ->  Task
#          Node: host=100.71.184.222 port=6432 dbname=icds_ucr
#          ->  Index Scan using awc_location_pkey_102840 on awc_location_102840 awc_location  (cost=0.68..51589.67 rows=55002 width=109)
#                Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
#                Filter: (aggregation_level = 5)
# (8 rows)

query_to_fetch_visit_data = """
    SELECT awc_id, CASE WHEN expected_visits>0 THEN valid_visits/(expected_visits)::float*100 ELSE 0 END as visits FROM agg_awc
    WHERE aggregation_level=5 AND state_id='f98e91aa003accb7b849a0f18ebd7039' AND aggregation_level=5 AND month='{month}'
"""


#                                                                              QUERY PLAN
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  Result  (cost=0.00..52851.49 rows=55801 width=41)
#    ->  Append  (cost=0.00..51595.97 rows=55801 width=41)
#          ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=40)
#                Filter: ((aggregation_level = 5) AND (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text) AND (month = '2020-01-01'::date))
#          ->  Index Scan using "agg_awc_2020-01-01_5_state_id_district_id_block_id_supervis_idx" on "agg_awc_2020-01-01_5"  (cost=0.68..51316.96 rows=55800 width=41)
#                Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
#                Filter: ((aggregation_level = 5) AND (month = '2020-01-01'::date))
# (7 rows)


@transaction.atomic
def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        row = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    return row


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        self.run_task()

    def run_task(self):
        start_date = date(2018, 10, 1)
        end_date = date(2020, 4, 1)
        columns = ['awc', 'awc_site_code', 'supervisor', 'district', 'block']
        date_itr = start_date
        count = 0
        while date_itr <= end_date:
            columns.append(date_itr.strftime("%Y-%m-%d"))
            date_itr = date_itr + relativedelta(months=1)
            count = count + 1
        awc_data = _run_custom_sql_script(query_to_fetch_awcs)
        data_format = {}
        for awc in awc_data:
            data_format.update({awc['doc_id']: [awc['awc_name'], awc['awc_site_code'], awc['supervisor_name'],
                                                awc['district_name'], awc['block_name']] + [0 for _ in
                                                                                            range(0, count)]})
        date_itr = start_date
        while date_itr <= end_date:
            visit_data = _run_custom_sql_script(
                query_to_fetch_visit_data.format(month=date_itr.strftime("%Y-%m-%d")))
            for row in visit_data:
                data_format[row['awc_id']][columns.index(date_itr.strftime("%Y-%m-%d"))] = row['visits']
            date_itr = date_itr + relativedelta(months=1)
        final_rows = [[columns]]
        for k in data_format:
            final_rows.append(data_format[k])
        fout = open(f'/home/cchq/AP_home_visit.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(final_rows)
