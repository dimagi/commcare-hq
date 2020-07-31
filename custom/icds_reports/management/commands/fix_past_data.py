import os
from datetime import date
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand
from corehq.util.argparse_types import date_type
from django.db import connections, transaction

from custom.icds_reports.utils.connections import get_icds_ucr_citus_db_alias


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
            'start_date',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD',
            nargs='?'
        )
        parser.add_argument(
            'script_number',
            type=int,
            help='The number of script running 1-8',
            nargs='?'
        )

    def build_data(self, monthly_date_dict, script_number):
        date = monthly_date_dict['record_date']
        print(f'\n======= Executing for month {date}======\n')
        for i in range(script_number, 8):
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
                # special case as second script contains multiple queries
                if i == 2:
                    sql_to_execute = sql_to_execute.split(';')
                    for j in range(0, len(sql_to_execute)):
                        _run_custom_sql_script(sql_to_execute[j])
                else:
                    _run_custom_sql_script(sql_to_execute)

    def handle(self, *args, **kwargs):
        # start date is the date from which we gonna start
        # by default its the start date of dashboard
        start_date = kwargs['start_date'] if kwargs['start_date'] else date(2017, 3, 1)
        # script number is to identify which script to run if we pause the command in between
        # by default its 1
        script_number = kwargs['script_number'] if kwargs['script_number'] else 1
        self.run_task(start_date, script_number)

    def run_task(self, start_date, script_number):
        monthly_dates_list = []
        part_tb_date_start = date(2017, 5, 1)
        part_tb_date_end = date(2019, 7, 1)
        end_date = date(2020, 5, 1)
        end_date = end_date.replace(day=1)
        # default is used to differentiate between the partitioned table monthly date
        # false -> month got a partitioned table
        # true -> month got a non partitioned table
        default = False
        date_itr = start_date
        while date_itr <= end_date:
            if date_itr >= part_tb_date_start and date_itr <= part_tb_date_end:
                default = True
            else:
                default = False
            monthly_date_dict = {"record_date": date_itr, "default": default}
            self.build_data(monthly_date_dict, script_number)
            date_itr = date_itr + relativedelta(months=1)
