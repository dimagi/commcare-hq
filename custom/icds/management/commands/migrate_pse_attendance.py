from __future__ import print_function

from django.core.management.base import BaseCommand

from django.db import connections


new_table = 'config_report_icds-cas_static-child_cases_monthly_v2_198ccc06'
old_table = 'config_report_icds-cas_static-child_cases_monthly_tabl_551fd064'

migration_query = """
UPDATE {new_table} B
SET
B.pse_daily_attendance = A.pse_days_attended,
B.pse_daily_attendance_male = CASE WHEN sex = 'M' THEN A.pse_days_attended ELSE NULL END,
B.pse_daily_attendance_female = CASE WHEN sex = 'F' THEN A.pse_days_attended ELSE NULL END
FROM {old_table} A
WHERE A.doc_id = B.doc_id and A.month = immutable_date_cast(B.month_start)
""".format(new_table=new_table, old_table=old_table)


class Command(BaseCommand):

    def handle(self, *args, **options):
        with connections['icds-ucr'].cursor() as cursor:
            print('Migrating pse data')
            cursor.execute(migration_query)
            print('Vacuuming table')
            cursor.execute("VACUUM ANALYZE {}".format(new_table))
