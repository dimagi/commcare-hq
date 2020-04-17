import os
from datetime import datetime
from dateutil.relativedelta import relativedelta


from django.core.management.base import BaseCommand
from corehq.util.argparse_types import date_type
from django.db import connections, transaction
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


@transaction.atomic
def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command, [])


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'month',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD'
        )

    def build_data(self, monthly_date_dict):
        date = monthly_date_dict['record_date']
        print(f'\n======= Executing for month {date}======\n')
        for i in range(1, 8):
            print(f'==============Executing Script {i} =============')
            if monthly_date_dict["default"] is False and i > 2:
                path = os.path.join(os.path.dirname(__file__), 'sql_scripts',
                                'fix_past_data_part_1_{}.sql'.format(i))
            else:
                path = os.path.join(os.path.dirname(__file__), 'sql_scripts',
                                    'fix_past_data_part_{}.sql'.format(i))
            with open(path, "r", encoding='utf-8') as sql_file:
                sql_to_execute = sql_file.read()
                sql_to_execute = sql_to_execute.format(start_date=date.strftime("%Y-%m-%d"))
                print(sql_to_execute)
                _run_custom_sql_script(sql_to_execute)

    def handle(self, *args, **kwargs):
        date = kwargs['month']
        self.run_task(date)


    def run_task(self, date):
        monthly_dates = []
        initial = datetime(2017, 3, 1, 0, 0)
        initial_2 = datetime(2017, 5, 1, 0, 0)
        initial_3 = datetime(2019, 8, 1, 0, 0)
        # date at which the partitioning breaks
        date_breaks = [initial_2, initial_3]
        # get the number of month intervals between the dates
        intervals = date.month - initial.month + 12 * (date.year - initial.year) + 1
        default = False
        for i in range(0, intervals):
            if initial in date_breaks:
                default = not default
            monthly_dates.append({"record_date": initial, "default": default})
            initial = initial + relativedelta(months=1)

        for monthly_date_dict in monthly_dates:
            self.build_data(monthly_date_dict)
