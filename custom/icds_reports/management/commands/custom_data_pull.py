import os
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
        file_object = open('/home/cchq/output.txt', 'a')
        file_object.write(f'{start_date.strftime("%Y-%m-%d")} \n\n')
        for row in rows:
            for k, v in row.items():
                file_object.write(f'{k} >> {v} \n')

        file_object.close()


    def handle(self, *args, **kwargs):
        self.run_task()

    def run_task(self):
        start_date = date(2018, 3, 1)
        end_date = date(2019, 3, 1)
        date_itr = start_date
        while date_itr <= end_date:
            self.write_to_file(self.build_data(date_itr), date_itr)
            date_itr = date_itr + relativedelta(months=1)
