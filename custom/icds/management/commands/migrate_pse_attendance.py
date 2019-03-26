from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from django.db import connections

from corehq.apps.userreports.util import get_table_name

new_table = get_table_name('icds-cas', 'static-child_cases_monthly_v2')
old_table = get_table_name('icds-cas', 'static-child_cases_monthly_tableau_v2')

migration_query = """
UPDATE "{new_table}" B
SET
pse_daily_attendance = A.pse_days_attended,
pse_daily_attendance_male = CASE WHEN sex = 'M' THEN A.pse_days_attended ELSE NULL END,
pse_daily_attendance_female = CASE WHEN sex = 'F' THEN A.pse_days_attended ELSE NULL END
FROM "{old_table}" A
WHERE A.doc_id = B.doc_id and A.month = immutable_date_cast(B.month_start)
""".format(new_table=new_table, old_table=old_table)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            dest='check',
            default=False,
            help="Print query and output from EXPLAIN"
        )

    def handle(self, check, **options):
        with connections['icds-ucr'].cursor() as cursor:
            if check:
                print('Query is')
                print(migration_query)
                print('-----------------------------')
                explain_result = cursor.execute("EXPLAIN {}".format(migration_query))
                print(explain_result)
            else:
                print('Migrating pse data')
                cursor.execute(migration_query)
                print('Vacuuming table')
                cursor.execute('VACUUM ANALYZE "{}"'.format(new_table))
