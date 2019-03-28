from __future__ import absolute_import, print_function, unicode_literals

from datetime import date

from dateutil.rrule import MONTHLY, rrule
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.connections import get_icds_ucr_db_alias


class Command(BaseCommand):
    def handle(self, *args, **options):
        start_date = date(2017, 3, 1)
        dates = [dt for dt in rrule(MONTHLY, dtstart=start_date, until=date(2019, 2, 1))]
        sql = """
        UPDATE {tablename} monthly SET
            supervisor_id = awc_loc.supervisor_id
        FROM awc_location awc_loc
        WHERE awc_loc.awc_id = monthly.awc_id AND monthly.supervisor_id IS NULL
        """

        for date_ in dates:
            date_string = date.isoformat()
            db_alias = get_icds_ucr_db_alias()
            if not db_alias:
                return

            with connections[db_alias].cursor() as cursor:
                tablename = "child_health_monthly_{}".format(date_string)
                print("Starting {}".format(tablename))
                cursor.execute(sql.format(tablename))

                tablename = "ccs_record_monthly_{}".format(date_string)
                print("Starting {}".format(tablename))
                cursor.execute(sql.format(tablename))
