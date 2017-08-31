from datetime import datetime
import logging
import os

from celery.schedules import crontab
from celery.task import periodic_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import connections

from corehq.util.decorators import serial_task

celery_task_logger = logging.getLogger('celery.task')


@periodic_task(run_every=crontab(minute=0, hour=21), acks_late=True, queue='background_queue')
def run_move_ucr_data_into_aggregation_tables_task(date=None):
    move_ucr_data_into_aggregation_tables.delay(date)


@serial_task('move-ucr-data-into-aggregate-tables', timeout=30 * 60, queue='background_queue')
def move_ucr_data_into_aggregation_tables(date=None, intervals=3):
    date = date or datetime.utcnow().date()
    monthly_date = date.replace(day=1)
    if hasattr(settings, "ICDS_UCR_DATABASE_ALIAS") and settings.ICDS_UCR_DATABASE_ALIAS:
        with connections[settings.ICDS_UCR_DATABASE_ALIAS].cursor() as cursor:

            path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'create_functions.sql')
            celery_task_logger.info("Starting icds reports create_functions")
            with open(path, "r") as sql_file:
                sql_to_execute = sql_file.read()
                cursor.execute(sql_to_execute)
            celery_task_logger.info("Ended icds reports create_functions")

            path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_locations_table.sql')
            celery_task_logger.info("Starting icds reports update_location_tables")
            with open(path, "r") as sql_file:
                sql_to_execute = sql_file.read()
                cursor.execute(sql_to_execute)
            celery_task_logger.info("Ended icds reports update_location_tables_sql")

            path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_monthly_aggregate_tables.sql')
            with open(path, "r") as sql_file:
                sql_to_execute = sql_file.read()
                for interval in range(intervals - 1, -1, -1):
                    calculation_date = (monthly_date - relativedelta(months=interval)).strftime('%Y-%m-%d')
                    celery_task_logger.info(
                        "Starting icds reports {} update_monthly_aggregate_tables".format(
                            calculation_date
                        )
                    )
                    cursor.execute(sql_to_execute, {"date": calculation_date})
                    celery_task_logger.info(
                        "Ended icds reports {} update_monthly_aggregate_tables".format(calculation_date)
                    )

            path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_daily_aggregate_table.sql')
            celery_task_logger.info("Starting icds reports update_daily_aggregate_table")
            with open(path, "r") as sql_file:
                sql_to_execute = sql_file.read()
                cursor.execute(sql_to_execute, {"date": date.strftime('%Y-%m-%d')})
            celery_task_logger.info("Ended icds reports update_daily_aggregate_table")
