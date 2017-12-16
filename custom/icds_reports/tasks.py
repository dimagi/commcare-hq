from __future__ import absolute_import

import uuid
from base64 import b64encode
from collections import namedtuple
from datetime import date, datetime, timedelta
import logging
import os

import pytz
from celery.schedules import crontab
from celery.task import periodic_task, task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import Error, IntegrityError, connections

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.util import send_report_download_email
from corehq.apps.settings.views import get_qrcode
from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.change_publishers import publish_case_saved
from corehq.util.decorators import serial_task
from corehq.util.soft_assert import soft_assert
from custom.icds_reports.reports.issnip_monthly_register import ISSNIPMonthlyReport
from custom.icds_reports.utils import zip_folder, create_pdf_file
from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception
from six.moves import range

celery_task_logger = logging.getLogger('celery.task')

UCRAggregationTask = namedtuple("UCRAggregationTask", ['type', 'date'])

DASHBOARD_TEAM_MEMBERS = ['jemord', 'lbagnoli', 'ssrikrishnan']
_dashboard_team_soft_assert = soft_assert(to=[
    '{}@{}'.format(member_id, 'dimagi.com') for member_id in DASHBOARD_TEAM_MEMBERS
])


@periodic_task(run_every=crontab(minute=0, hour=21), acks_late=True, queue='background_queue')
def run_move_ucr_data_into_aggregation_tables_task(date=None):
    move_ucr_data_into_aggregation_tables.delay(date)


@serial_task('move-ucr-data-into-aggregate-tables', timeout=30 * 60, queue='background_queue')
def move_ucr_data_into_aggregation_tables(date=None, intervals=2):
    date = date or datetime.utcnow().date()
    monthly_dates = []

    first_day_of_month = date.replace(day=1)
    for interval in range(intervals - 1, 0, -1):
        # calculate the last day of the previous months to send to the aggregation script
        first_day_next_month = first_day_of_month - relativedelta(months=interval - 1)
        monthly_dates.append(first_day_next_month - relativedelta(days=1))

    monthly_dates.append(date)

    if hasattr(settings, "ICDS_UCR_DATABASE_ALIAS") and settings.ICDS_UCR_DATABASE_ALIAS:
        with connections[settings.ICDS_UCR_DATABASE_ALIAS].cursor() as cursor:
            _create_aggregate_functions(cursor)
            _update_aggregate_locations_tables(cursor)

        aggregation_tasks = []

        for monthly_date in monthly_dates:
            calculation_date = monthly_date.strftime('%Y-%m-%d')
            aggregation_tasks.append(UCRAggregationTask('monthly', calculation_date))

        aggregation_tasks.append(UCRAggregationTask('daily', date.strftime('%Y-%m-%d')))
        aggregate_tables.delay(aggregation_tasks[0], aggregation_tasks[1:])


def _create_aggregate_functions(cursor):
    try:
        path = os.path.join(os.path.dirname(__file__), 'migrations', 'sql_templates', 'create_functions.sql')
        celery_task_logger.info("Starting icds reports create_functions")
        with open(path, "r") as sql_file:
            sql_to_execute = sql_file.read()
            cursor.execute(sql_to_execute)
        celery_task_logger.info("Ended icds reports create_functions")
    except Exception:
        # This is likely due to a change in the UCR models or aggregation script which should be rare
        # First step would be to look through this error to find what function is causing the error
        # and look for recent changes in this folder.
        _dashboard_team_soft_assert(False, "Unexpected occurred while creating functions in dashboard aggregation")
        raise


def _update_aggregate_locations_tables(cursor):
    try:
        path = os.path.join(os.path.dirname(__file__), 'sql_templates', 'update_locations_table.sql')
        celery_task_logger.info("Starting icds reports update_location_tables")
        with open(path, "r") as sql_file:
            sql_to_execute = sql_file.read()
            cursor.execute(sql_to_execute)
        celery_task_logger.info("Ended icds reports update_location_tables_sql")
    except IntegrityError:
        # This has occurred when there's a location upload, but not all locations were updated.
        # Some more details are here https://github.com/dimagi/commcare-hq/pull/18839
        # It's usually fixed by rebuild the location UCR table and running this task again, but
        # that PR should fix that issue
        _dashboard_team_soft_assert(False, "Error occurred while aggregating locations")
        raise
    except Exception:
        # I'm not sure what this one will be
        _dashboard_team_soft_assert(
            False, "Unexpected occurred while aggregating locations in dashboard aggregation")
        raise


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
                    _dashboard_team_soft_assert(
                        False,
                        "{} aggregation failed on {} for {}. This task will be retried in 15 minutes".format(
                            aggregation_type, settings.SERVER_ENVIRONMENT, aggregation_date
                        )
                    )
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
        _dashboard_team_soft_assert(False, "Aggregation completed on {}".format(settings.SERVER_ENVIRONMENT))
        celery_task_logger.info("Aggregation has completed")


@periodic_task(
    queue='background_queue',
    run_every=crontab(day_of_week='sunday', minute=0, hour=21),
    acks_late=True
)
def recalculate_stagnant_cases():
    domain = 'icds-cas'
    config_ids = [
        'static-icds-cas-static-ccs_record_cases_monthly_v2',
        'static-icds-cas-static-ccs_record_cases_monthly_tableau_v2',
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


india_timezone = pytz.timezone('Asia/Kolkata')


@task(queue='background_queue', ignore_result=True)
def prepare_issnip_monthly_register_reports(domain, user, awcs, pdf_format, month, year):
    dir_name = uuid.uuid4()

    utc_now = datetime.now(pytz.utc)
    india_now = utc_now.astimezone(india_timezone)

    base_dir = os.path.join(settings.BASE_DIR, 'custom/icds_reports/static/media/')
    directory = os.path.dirname(os.path.join(base_dir, dir_name.hex + '/'))

    selected_date = date(year, month, 1)

    report_context = {
        'reports': []
    }

    if not os.path.exists(directory):
        os.makedirs(directory)
    for awc in awcs:
        awc_location = SQLLocation.objects.get(location_id=awc)
        report = ISSNIPMonthlyReport(config={
            'awc_id': awc_location.location_id,
            'month': selected_date,
            'domain': domain
        })
        qrcode = get_qrcode("{} {}".format(
            awc_location.site_code,
            india_now.strftime('%d %b %Y')
        ))
        context = {
            'qrcode_64': b64encode(qrcode),
            'report': report
        }

        if pdf_format == 'one':
            report_context['reports'].append(context)
        else:
            report_context['reports'] = [context]
            create_pdf_file(
                'ISSNIP_monthly_register_{}'.format(awc_location.name.replace(' ', '_')),
                directory,
                report_context
            )

    if pdf_format == 'many':
        zip_folder(base_dir, dir_name.hex)
    else:
        create_pdf_file('ISSNIP_monthly_register_cumulative', directory, report_context)

    send_report_download_email('ISSNIP monthly register', user, 'test')
    icds_remove_files.apply_async(args=[dir_name.hex, base_dir, pdf_format], countdown=60)


@task(queue='background_queue', ignore_result=True)
def icds_remove_files(uuid, folder_dir, pdf_format):
    reports_dir = os.path.join(folder_dir, uuid)
    for root, dirs, files in os.walk(reports_dir):
        for name in files:
            os.remove(os.path.join(root, name))
    if pdf_format == 'many':
        os.remove(os.path.join(folder_dir, "{}.zip").format(uuid))
    os.rmdir(reports_dir)
