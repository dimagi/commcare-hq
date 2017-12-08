from __future__ import absolute_import
from collections import namedtuple
from datetime import datetime, timedelta
import logging
import os

from celery.schedules import crontab
from celery.task import periodic_task, task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import Error, connections

from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.change_publishers import publish_case_saved
from corehq.util.decorators import serial_task
from corehq.util.soft_assert import soft_assert
from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception
from six.moves import range

celery_task_logger = logging.getLogger('celery.task')

UCRAggregationTask = namedtuple("UCRAggregationTask", ['type', 'date'])

DASHBOARD_TEAM_MEMBERS = ['jemord', 'lbagnoli', 'ssrikrishnan']


@periodic_task(run_every=crontab(minute=0, hour=21), acks_late=True, queue='background_queue')
def run_move_ucr_data_into_aggregation_tables_task(date=None):
    move_ucr_data_into_aggregation_tables.delay(date)


@serial_task('move-ucr-data-into-aggregate-tables', timeout=30 * 60, queue='background_queue')
def move_ucr_data_into_aggregation_tables(date=None, intervals=2):
    date = date or datetime.utcnow().date()
    monthly_date = date.replace(day=1)
    if hasattr(settings, "ICDS_UCR_DATABASE_ALIAS") and settings.ICDS_UCR_DATABASE_ALIAS:
        with connections[settings.ICDS_UCR_DATABASE_ALIAS].cursor() as cursor:
            _create_aggregate_functions(cursor)
            _update_aggregate_locations_tables(cursor)

        aggregation_tasks = []

        for interval in range(intervals - 1, -1, -1):
            calculation_date = (monthly_date - relativedelta(months=interval)).strftime('%Y-%m-%d')
            aggregation_tasks.append(UCRAggregationTask('monthly', calculation_date))

        aggregation_tasks.append(UCRAggregationTask('daily', date.strftime('%Y-%m-%d')))
        aggregate_tables.delay(aggregation_tasks[0], aggregation_tasks[1:])


def _create_aggregate_functions(cursor):
    path = os.path.join(os.path.dirname(__file__), 'migrations', 'sql_templates', 'create_functions.sql')
    celery_task_logger.info("Starting icds reports create_functions")
    with open(path, "r") as sql_file:
        sql_to_execute = sql_file.read()
        cursor.execute(sql_to_execute)
    celery_task_logger.info("Ended icds reports create_functions")


def _update_aggregate_locations_tables(cursor):
    path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_locations_table.sql')
    celery_task_logger.info("Starting icds reports update_location_tables")
    with open(path, "r") as sql_file:
        sql_to_execute = sql_file.read()
        cursor.execute(sql_to_execute)
    celery_task_logger.info("Ended icds reports update_location_tables_sql")


@task(queue='background_queue', bind=True, default_retry_delay=15 * 60, acks_late=True)
def aggregate_tables(self, current_task, future_tasks):
    aggregation_type = current_task.type
    aggregation_date = current_task.date

    if aggregation_type == 'monthly':
        path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_monthly_aggregate_tables.sql')
    elif aggregation_type == 'daily':
        path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_daily_aggregate_table.sql')
    else:
        raise ValueError("Invalid aggregation type {}".format(aggregation_type))

    if hasattr(settings, "ICDS_UCR_DATABASE_ALIAS") and settings.ICDS_UCR_DATABASE_ALIAS:
        with connections[settings.ICDS_UCR_DATABASE_ALIAS].cursor() as cursor:
            with open(path, "r") as sql_file:
                sql_to_execute = sql_file.read()
                celery_task_logger.info(
                    "Starting icds reports {} update_{}_aggregate_tables".format(
                        aggregation_date, aggregation_type
                    )
                )

                try:
                    cursor.execute(sql_to_execute, {"date": aggregation_date})
                except Error as exc:
                    notify_exception(
                        None,
                        message="Error occurred during ICDS aggregation",
                        details={
                            'type': aggregation_type,
                            'date': aggregation_date,
                            'error': exc,
                        }
                    )
                    self.retry(exc=exc)

                celery_task_logger.info(
                    "Ended icds reports {} update_{}_aggregate_tables".format(
                        aggregation_date, aggregation_type
                    )
                )

    if future_tasks:
        aggregate_tables.delay(future_tasks[0], future_tasks[1:])
    else:
        # temporary soft assert to verify it's completing
        _soft_assert = soft_assert(to=[
            '{}@{}'.format(member_id, 'dimagi.com') for member_id in DASHBOARD_TEAM_MEMBERS
        ])
        _soft_assert(False, "Aggregation completed on {}".format(settings.SERVER_ENVIRONMENT))
        celery_task_logger.info("Aggregation has completed")


@periodic_task(
    queue='background_queue',
    run_every=crontab(day_of_week='sunday', minute=0, hour=21),
    acks_late=True
)
def recalculate_stagnant_cases():
    domain = 'icds-cas'
    config_ids = [
        'static-icds-cas-static-ccs_record_cases_monthly',
        'static-icds-cas-static-ccs_record_cases_monthly_v2',
        'static-icds-cas-static-ccs_record_cases_monthly_tableau_v2',
        'static-icds-cas-static-child_cases_monthly',
        'static-icds-cas-static-child_cases_monthly_v2',
        'static-icds-cas-static-child_cases_monthly_tableau_v2',
    ]

    stagnant_cases = set()

    for config_id in config_ids:
        config, is_static = get_datasource_config(config_id, domain)
        adapter = get_indicator_adapter(config)
        case_ids = _find_stagnant_cases(adapter)
        celery_task_logger.info(
            "Found {} stagnant cases in config {}".format(len(case_ids), config_id)
        )
        stagnant_cases = stagnant_cases.union(set(case_ids))
        celery_task_logger.info(
            "Total number of stagant cases is now {}".format(len(stagnant_cases))
        )

    case_accessor = CaseAccessors(domain)
    num_stagnant_cases = len(stagnant_cases)
    current_case_num = 0
    for case_ids in chunked(stagnant_cases, 1000):
        current_case_num += len(case_ids)
        cases = case_accessor.get_cases(list(case_ids))
        for case in cases:
            publish_case_saved(case, send_post_save_signal=False)
        celery_task_logger.info(
            "Resaved {} / {} cases".format(current_case_num, num_stagnant_cases)
        )


def _find_stagnant_cases(adapter):
    stagnant_date = datetime.utcnow() - timedelta(days=45)
    table = adapter.get_table()
    query = adapter.get_query_object()
    query = query.with_entities(table.columns.doc_id).filter(
        table.columns.inserted_at <= stagnant_date
    ).distinct()
    return query.all()
