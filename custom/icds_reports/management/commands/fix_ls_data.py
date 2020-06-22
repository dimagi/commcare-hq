import os
from django.core.management.base import BaseCommand

from datetime import date
from dateutil.relativedelta import relativedelta
from corehq.util.argparse_types import date_type
from corehq.apps.userreports.util import get_table_name
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
            'start_date',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD',
            nargs='?'
        )

    def fix_intial_table(self, month, next_month_start):
        ls_usage_ucr = get_table_name('icds-cas', 'static-ls_usage_forms')
        tablename = self._tablename_func(4, month)
        path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'fix_past_data.sql')
        with open(path, "r", encoding='utf-8') as sql_file:
            sql_to_execute = sql_file.read()
            sql_to_execute = sql_to_execute.format(ls_usage_ucr=ls_usage_ucr, tablename=tablename,
                                                   next_month_start=next_month_start)
            sql_to_execute = sql_to_execute.split(';')
            for j in range(0, len(sql_to_execute)):
                _run_custom_sql_script(sql_to_execute[j])

    def rollup_query_data(self, month):
        rollup_queries = [self.rollup_query(i, month) for i in range(3, 0, -1)]
        for query in rollup_queries:
            _run_custom_sql_script(query)

    def handle(self, *args, **kwargs):
        start_date = kwargs['start_date'] if kwargs['start_date'] else date(2017, 3, 1)
        end_date = date(2020, 1, 1)
        month = start_date
        while month < end_date:
            next_month_start = month + relativedelta(months=1)
            month = month + relativedelta(months=1)
            self.fix_intial_table(month, next_month_start)
            self.rollup_query_data(month)

    def _tablename_func(self, agg_level, month):
        return "{}_{}_{}".format('agg_ls', month.strftime("%Y-%m-%d"), agg_level)

    def rollup_query(self, agg_level, month):
        locations = ['state_id', 'district_id', 'block_id', 'supervisor_id']

        for i in range(3, agg_level - 1, -1):
            locations[i] = "'All'"

        return """
            UPDATE "{to_table}" ls
            SET
            ls.num_supervisor_launched = ut.num_supervisor_launched
            FROM (
                SELECT
                {update_location},
                sum(num_supervisor_launched) as num_supervisor_launched
                FROM "{from_table}"
                GROUP BY {group_by}, month
            ) ut
            WHERE ls.{update_location} = ut.{update_location}
            
        """.format(
            agg_level=agg_level,
            to_table=self._tablename_func(agg_level, month),
            from_table=self._tablename_func(agg_level + 1, month),
            group_by=','.join(locations[:agg_level]),
            update_location=locations[agg_level - 1],
            month=month.strftime("%Y-%m-%d")
        )
