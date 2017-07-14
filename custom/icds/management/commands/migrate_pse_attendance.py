from __future__ import print_function

from django.core.management.base import BaseCommand

from django.db import connections


new_table = 'config_report_icds-cas_static-child_cases_monthly_v2_198ccc06'
old_table = 'config_report_icds-cas_static-child_cases_monthly_tabl_551fd064'

male_sql_query = """
INSERT INTO {new_table} (pse_daily_attendance, pse_daily_attendance_male)
SELECT pse_days_attended, pse_days_attended
FROM {old_table} A
LEFT JOIN {new_table} B
ON A.doc_id = B.doc_id and A.month_start = B.month_start
WHERE B.sex = 'F'
""".format(new_table=new_table, old_table=old_table)

female_sql_query = """
INSERT INTO {new_table} (pse_daily_attendance, pse_daily_attendance_female)
SELECT pse_days_attended, pse_days_attended
FROM {old_table} A
LEFT JOIN {new_table} B
ON A.doc_id = B.doc_id and A.month_start = B.month_start
WHERE B.sex = 'M'
""".format(new_table=new_table, old_table=old_table)

class Command(BaseCommand):

    def handle(self, *args, **options):
        with connections['icds-ucr'].cursor() as cursor:
            print('Migrating male data')
            cursor.execute(male_sql_query)
            print('Migrating female data')
            cursor.execute(female_sql_query)
