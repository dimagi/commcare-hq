import os
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from corehq.util.argparse_types import date_type
from custom.icds_reports.tasks import icds_state_aggregation_task, _agg_bihar_api_demographics

DASHBOARD_DOMAIN = 'icds-cas'
STATE_ID = 'f9b47ea2ee2d8a02acddeeb491d3e175'


def _run_custom_sql_script(command, day=None):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command, [day])


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'start_date',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD',
            nargs='?'
        )

    def build_bp_data(self, month):
        if month.strftime("%Y-%m-%d") == '2020-03-01':
            path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'build_bp_initial_data.sql')
            with open(path, "r", encoding='utf-8') as sql_file:
                sql_to_execute = sql_file.read()
                sql_to_execute = sql_to_execute.format(month=month.strftime("%Y-%m-%d"), state_id=STATE_ID)
                sql_to_execute = sql_to_execute.split(';')
                for i in range(0, len(sql_to_execute)):
                    _run_custom_sql_script(sql_to_execute[i])
        else:
            icds_state_aggregation_task(state_id=STATE_ID, date=month,
                                        func_name='_aggregate_bp_forms')

    def build_pnc_data(self, month):
        if month.strftime("%Y-%m-%d") == '2020-03-01':
            path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'build_pnc_initial_data.sql')
            with open(path, "r", encoding='utf-8') as sql_file:
                sql_to_execute = sql_file.read()
                sql_to_execute = sql_to_execute.format(month=month.strftime("%Y-%m-%d"), state_id=STATE_ID)
                sql_to_execute = sql_to_execute.split(';')
                for i in range(0, len(sql_to_execute)):
                    _run_custom_sql_script(sql_to_execute[i])
        else:
            icds_state_aggregation_task(state_id=STATE_ID, date=month,
                                        func_name='_aggregate_ccs_record_pnc_forms')

    def update_ccs_data(self, month):
        path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'update_ccs_data.sql')
        with open(path, "r", encoding='utf-8') as sql_file:
            sql_to_execute = sql_file.read()
            sql_to_execute = sql_to_execute.format(month=month.strftime("%Y-%m-%d"), state_id=STATE_ID)
            sql_to_execute = sql_to_execute.split(';')
            for i in range(0, len(sql_to_execute)):
                _run_custom_sql_script(sql_to_execute[i])

    def handle(self, *args, **options):
        start_date = options['start_date'] if options['start_date'] else date(2020, 3, 1)
        end_date = date(2020, 5, 1)
        date_itr = start_date
        while date_itr <= end_date:
            print(f"Runnning for month {date_itr}=====================\n")
            self.build_bp_data(date_itr)
            self.build_pnc_data(date_itr)
            self.update_ccs_data(date_itr)
            _agg_bihar_api_demographics(date_itr)
            date_itr = date_itr + relativedelta(months=1)
