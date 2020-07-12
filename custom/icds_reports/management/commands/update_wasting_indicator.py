import os
import datetime
from dateutil import relativedelta
from django.core.management.base import BaseCommand

from django.db import connections, transaction

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


@transaction.atomic
def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return

    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)


class Command(BaseCommand):
    def handle(self, *args, **options):
        start_date = datetime.date(2020, 5, 1)
        path = os.path.join(
            os.path.dirname(__file__), 'sql_scripts', 'fix_wasting_child.sql'
        )

        initial_month = datetime.date(2017, 3, 1)
        with open(path, "r", encoding='utf-8') as sql_file:
            sql_to_execute = sql_file.read()

        while start_date >=initial_month:
            print("PROCESSING MONTH {}".format(start_date))
            query = sql_to_execute.format(month=start_date)
            _run_custom_sql_script(query)
            start_date -=  relativedelta(months=1)
