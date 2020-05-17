import os
import csv
from datetime import date
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand
from django.db import connections, transaction
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias

@transaction.atomic
def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    row = ''
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        row = dict(zip([column[0] for column in cursor.description], cursor.fetchone()))
    return row

class Command(BaseCommand):

    def build_data(self, start_date):
        rows = []
        path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'urgent_pmo_datapull.sql')
        with open(path, "r", encoding='utf-8') as sql_file:
            sql_to_execute = sql_file.read()
            sql_to_execute = sql_to_execute.format(month=start_date.strftime("%Y-%m-%d"))
            sql_to_execute = sql_to_execute.split(';')
            for j in range(0, len(sql_to_execute)):
                rows.append(_run_custom_sql_script(sql_to_execute[j]))
        return rows

    def write_to_file(self, rows, start_date):
        ret_row = [start_date.strftime("%Y-%m-%d")]
        for row in rows:
            for k, v in row.items():
                ret_row.append(v)
        return ret_row


    def handle(self, *args, **kwargs):
        self.run_task()

    def run_task(self):
        start_date = date(2018, 3, 1)
        end_date = date(2020, 3, 1)
        date_itr = start_date
        final_rows = [['month', 'child_pse', 'child_hcm', 'child_thr', 'height_weight_measured_in_month', 'bf_at_birth', 'born_in_month', 'cf_initiation_in_month', 'cf_initiation_eligible', 'nutrition_status_weighed', 'wasting_severe', 'wasting_moderate', 'weighed_and_height_measured_in_month', 'ebf_in_month', 'underweight_children', 'immunization', 'wer_eligible_child_health', 'mother_thr', 'pw_lw_enrolled', 'counsel_immediatebf_isto_trimester_3', 'days_opened', 'launched', 'avg_days_opened', 'total_household', 'launched_states', 'launched_districts', 'launched_blocks', 'num_awcs_conducted_cbe', 'num_awcs_conducted_vhnd', 'incentive_eligible', 'awh_eligible', 'child_0_36', 'child_36_72', 'child_72', 'valid_visits', 'expected_visits', 'exp_isto_valid', 'wer_eligble_isto_wer_weighed']]
        while date_itr <= end_date:
            row = self.write_to_file(self.build_data(date_itr), date_itr)
            final_rows.append(row)
            date_itr = date_itr + relativedelta(months=1)
        fout = open('/home/cchq/National_issnip_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(final_rows)
