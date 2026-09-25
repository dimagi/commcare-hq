import os
import datetime

from dateutil.rrule import rrule, MONTHLY
from django.core.management.base import BaseCommand

from django.db import connections, transaction

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
import dateutil
from psycopg2.extensions import AsIs

@transaction.atomic
def _run_custom_sql_script(command, params):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return

    with connections[db_alias].cursor() as cursor:
        cursor.execute(command, params)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--start',
            action='store',
            help='Only include data modified after this date',
        )
        parser.add_argument(
            '--end',
            action='store',
            help='Only include data modified before this date')

    def handle(self, *args, **options):
        start = dateutil.parser.parse(options['start']) if options['start'] else datetime(2018, 3, 1)
        end = dateutil.parser.parse(options['end']) if options['end'] else datetime.utcnow()

        dates = [dt for dt in rrule(MONTHLY, dtstart=start, until=end)]
        path = os.path.join(
            os.path.dirname(__file__), 'sql_scripts', 'update_cbe_vhnd_agg_awc.sql'
        )
        with open(path, "r", encoding='utf-8') as sql_file:
            sql_query = sql_file.read()

        for date in dates:
            month_string = date.strftime("%Y-%m-%d")
            table_name = f'agg_awc_{month_string}'
            _run_custom_sql_script(
                sql_query, {'tablename': AsIs(table_name), 'query_month': month_string}
            )
            print(f"Done for month {month_string}")
