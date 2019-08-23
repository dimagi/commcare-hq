
import os
import datetime

from dateutil.rrule import rrule, MONTHLY
from django.core.management.base import BaseCommand

from django.db import connections, transaction

from corehq.sql_db.connections import get_icds_ucr_db_alias
from io import open


@transaction.atomic
def _run_custom_sql_script(command, day=None):
    db_alias = get_icds_ucr_db_alias()
    if not db_alias:
        return

    with connections[db_alias].cursor() as cursor:
        cursor.execute(command, [day])


class Command(BaseCommand):
    def handle(self, *args, **options):
        start_date = datetime.date(2017, 3, 1)
        dates = [dt for dt in rrule(MONTHLY, dtstart=start_date, until=datetime.datetime.utcnow())]
        path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'update_child_health_monthly.sql')
        with open(path, "r", encoding='utf-8') as sql_file:
            sql_to_execute = sql_file.read()
            _run_custom_sql_script(sql_to_execute)

        for date in dates:
            _run_custom_sql_script(
                'SELECT update_child_health_monthly(%s);', date.date()
            )

        _run_custom_sql_script("DROP FUNCTION update_child_health_monthly(date);")
