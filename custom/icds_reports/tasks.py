from __future__ import absolute_import

from base64 import b64encode
from collections import namedtuple
import csv
from datetime import date, datetime, timedelta
import io
import logging
import os
import uuid

from celery.schedules import crontab
from celery.task import periodic_task, task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import Error, IntegrityError, connections
from django.db.models import F
import pytz

from corehq.apps.locations.models import SQLLocation
from corehq.apps.settings.views import get_qrcode
from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.const import SERVER_DATE_FORMAT
from corehq.form_processor.change_publishers import publish_case_saved
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.sql_db.connections import get_icds_ucr_db_alias
from corehq.util.decorators import serial_task
from corehq.util.log import send_HTML_email
from corehq.util.soft_assert import soft_assert
from corehq.util.view_utils import reverse
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.reports.issnip_monthly_register import ISSNIPMonthlyReport
from custom.icds_reports.utils import zip_folder, create_pdf_file
from dimagi.utils.chunked import chunked
from dimagi.utils.dates import force_to_date
from dimagi.utils.logging import notify_exception
from six.moves import range

celery_task_logger = logging.getLogger('celery.task')

UCRAggregationTask = namedtuple("UCRAggregationTask", ['type', 'date'])

DASHBOARD_TEAM_MEMBERS = ['jemord', 'lbagnoli', 'ssrikrishnan', 'mharrison']
DASHBOARD_TEAM_EMAILS = ['{}@{}'.format(member_id, 'dimagi.com') for member_id in DASHBOARD_TEAM_MEMBERS]
_dashboard_team_soft_assert = soft_assert(to=DASHBOARD_TEAM_EMAILS)


@periodic_task(run_every=crontab(minute=30, hour=23), acks_late=True, queue='background_queue')
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

    db_alias = get_icds_ucr_db_alias()
    if db_alias:
        with connections[db_alias].cursor() as cursor:
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

    db_alias = get_icds_ucr_db_alias()
    if db_alias:
        with connections[db_alias].cursor() as cursor:
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
        icds_data_validation.delay(aggregation_date)


@periodic_task(
    queue='background_queue',
    run_every=crontab(day_of_week='tuesday,thursday,saturday', minute=0, hour=21),
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
    stagnant_date = datetime.utcnow() - timedelta(days=26)
    table = adapter.get_table()
    query = adapter.get_query_object()
    query = query.with_entities(table.columns.doc_id).filter(
        table.columns.inserted_at <= stagnant_date
    ).distinct()
    return query.all()


india_timezone = pytz.timezone('Asia/Kolkata')


@task(queue='background_queue')
def prepare_issnip_monthly_register_reports(domain, user, awcs, pdf_format, month, year):

    utc_now = datetime.now(pytz.utc)
    india_now = utc_now.astimezone(india_timezone)

    selected_date = date(year, month, 1)
    report_context = {
        'reports': []
    }

    pdf_files = []

    for awc in awcs:
        pdf_hash = uuid.uuid4().hex

        awc_location = SQLLocation.objects.get(location_id=awc)
        pdf_files.append({
            'uuid': pdf_hash,
            'location_name': awc_location.name.replace(' ', '_')
        })
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
                pdf_hash,
                report_context
            )

    if pdf_format == 'many':
        cache_key = zip_folder(pdf_files)
    else:
        cache_key = create_pdf_file(uuid.uuid4().hex, report_context)

    params = {
        'domain': domain,
        'uuid': cache_key,
        'format': pdf_format
    }

    return {
        'domain': domain,
        'uuid': cache_key,
        'format': pdf_format,
        'link': reverse('icds_download_pdf', params=params, absolute=True, kwargs={'domain': domain})
    }


@task(queue='background_queue')
def icds_data_validation(day):
    """Checks all AWCs to validate that there will be no inconsistencies in the
    reporting dashboard.
    """

    # agg tables store the month like YYYY-MM-01
    month = force_to_date(day)
    month.replace(day=1)
    return_values = ('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name')

    bad_wasting_awcs = AggChildHealthMonthly.objects.filter(
        month=month, aggregation_level=5
    ).exclude(
        weighed_and_height_measured_in_month=(
            F('wasting_moderate') + F('wasting_severe') + F('wasting_normal')
        )
    ).values_list(*return_values)

    bad_stunting_awcs = AggChildHealthMonthly.objects.filter(month=month, aggregation_level=5).exclude(
        height_measured_in_month=(
            F('stunting_severe') + F('stunting_moderate') + F('stunting_normal')
        )
    ).values_list(*return_values)

    bad_underweight_awcs = AggChildHealthMonthly.objects.filter(month=month, aggregation_level=5).exclude(
        nutrition_status_weighed=(
            F('nutrition_status_normal') +
            F('nutrition_status_moderately_underweight') +
            F('nutrition_status_severely_underweight')
        )
    ).values_list(*return_values)

    bad_lbw_awcs = AggChildHealthMonthly.objects.filter(month=month, aggregation_level=5).exclude(
        weighed_and_born_in_month__gt=(
            F('low_birth_weight_in_month')
        )
    ).values_list(*return_values)

    csv_file = io.BytesIO()
    writer = csv.writer(csv_file)
    writer.writerow(('type',) + return_values)
    _icds_add_awcs_to_file(writer, 'wasting', bad_wasting_awcs)
    _icds_add_awcs_to_file(writer, 'stunting', bad_stunting_awcs)
    _icds_add_awcs_to_file(writer, 'underweight', bad_underweight_awcs)
    _icds_add_awcs_to_file(writer, 'low_birth_weight', bad_lbw_awcs)

    email_content = """
    Incorrect wasting AWCs: {bad_wasting_awcs}
    Incorrect stunting AWCs: {bad_stunting_awcs}
    Incorrect underweight AWCs: {bad_underweight_awcs}
    Incorrect low birth weight AWCs: {bad_lbw_awcs}

    Please see attached file for more details
    """.format(
        bad_wasting_awcs=len(bad_wasting_awcs),
        bad_stunting_awcs=len(bad_stunting_awcs),
        bad_underweight_awcs=len(bad_underweight_awcs),
        bad_lbw_awcs=len(bad_lbw_awcs),
    )

    filename = month.strftime('validation_results_%s.csv' % SERVER_DATE_FORMAT)
    send_HTML_email(
        'ICDS Dashboard Validation Results', DASHBOARD_TEAM_EMAILS, email_content,
        file_attachments=[{'file_obj': csv_file, 'title': filename, 'mimetype': 'text/csv'}],
    )


def _icds_add_awcs_to_file(csv_writer, error_type, rows):
    for row in rows:
        csv_writer.writerow((error_type, ) + row)
