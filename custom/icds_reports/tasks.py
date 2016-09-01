import os

from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from django.db import connections


@periodic_task(run_every=crontab(minute=0, hour=0, day_of_week=7), acks_late=True)
def move_ucr_data_into_aggregation_tables():
    with connections[settings.ICDS_UCR_DATABASE_ALIAS].cursor() as cursor:

        path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_locations_table.sql')
        with open(path, "r") as sql_file:
            sql_to_execute = sql_file.read()
            cursor.execute(sql_to_execute)

        path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_monthly_aggregate_tables.sql')
        with open(path, "r") as sql_file:
            sql_to_execute = sql_file.read()
            for interval in ["0 months", "1 months", "2 months"]:
                cursor.execute(sql_to_execute, {"interval": interval})

