import os
from datetime import datetime


from django.core.management.base import BaseCommand
from corehq.util.argparse_types import date_type
from django.db import connections, transaction
from custom.icds_reports.tasks import _get_monthly_dates
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


@transaction.atomic
def _run_custom_sql_script(command, day=None):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command, [day])


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'month',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD'
        )

    def build_data(self, date):
        for i in range(1, 4):
            path = os.path.join(os.path.dirname(__file__), 'sql_scripts',
                                'ap_data_pull_{}.sql'.format(i))
            context = {
                'month_execute': date.strftime("%Y-%m-%d")
            }
            with open(path, "r", encoding='utf-8') as sql_file:
                sql_to_execute = sql_file.read()
                sql_to_execute = sql_to_execute % context
                print(f"Executing Pull ap_date_pull_{i}\n")
                _run_custom_sql_script(sql_to_execute)

    def handle(self, *args, **kwargs):
        date = kwargs['month']
        self.run_task(date)

    def run_task(self, date):
        initial_date = datetime(2019, 4, 1, 0, 0)
        intervals = date.month - initial_date.month + 12 * (date.year - initial_date.year) + 1
        monthly_dates = _get_monthly_dates(date, total_intervals=intervals)
        for monthly_date in monthly_dates:
            self.build_data(monthly_date)
