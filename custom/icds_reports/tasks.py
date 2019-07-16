from __future__ import absolute_import, unicode_literals

import io
import logging
import os
import re
import pytz
import tempfile
import zipfile
from collections import namedtuple
from datetime import date, datetime, timedelta
from io import BytesIO, open

from django.conf import settings
from django.db import Error, IntegrityError, connections, transaction
from django.db.models import F

import csv342 as csv
import six
from celery import chain
from celery.schedules import crontab
from celery.task import periodic_task, task
from dateutil.relativedelta import relativedelta
from dateutil import parser as date_parser
from six.moves import range

from couchexport.export import export_from_tables
from dimagi.utils.chunked import chunked
from dimagi.utils.dates import force_to_date
from dimagi.utils.logging import notify_exception

from corehq import toggles
from corehq.apps.data_pipeline_audit.dbacessors import (
    get_es_counts_by_doc_type,
    get_primary_db_case_counts,
    get_primary_db_form_counts,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_user_id_username_pairs_by_domain,
)
from corehq.const import SERVER_DATE_FORMAT
from corehq.form_processor.change_publishers import publish_case_saved
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.sql_db.connections import get_icds_ucr_db_alias, get_icds_ucr_citus_db_alias, \
    get_icds_ucr_db_alias_or_citus
from corehq.sql_db.routers import db_for_read_write, force_citus_engine, forced_citus
from corehq.util.datadog.utils import case_load_counter, create_datadog_event
from corehq.util.decorators import serial_task
from corehq.util.log import send_HTML_email
from corehq.util.soft_assert import soft_assert
from corehq.util.view_utils import reverse
from custom.icds_reports.const import (
    AWC_INFRASTRUCTURE_EXPORT,
    AWW_INCENTIVE_REPORT,
    BENEFICIARY_LIST_EXPORT,
    CHILDREN_EXPORT,
    DASHBOARD_DOMAIN,
    DEMOGRAPHICS_EXPORT,
    LS_REPORT_EXPORT,
    PREGNANT_WOMEN_EXPORT,
    SYSTEM_USAGE_EXPORT,
    THREE_MONTHS,
    INDIA_TIMEZONE,
    THR_REPORT_EXPORT
)
from custom.icds_reports.experiment import DashboardQueryExperiment
from custom.icds_reports.models import (
    AggAwc,
    AggCcsRecord,
    AggChildHealth,
    AggChildHealthMonthly,
    AggLs,
    AggregateAwcInfrastructureForms,
    AggregateBirthPreparednesForms,
    AggregateCcsRecordComplementaryFeedingForms,
    AggregateCcsRecordDeliveryForms,
    AggregateCcsRecordPostnatalCareForms,
    AggregateCcsRecordTHRForms,
    AggregateChildHealthDailyFeedingForms,
    AggregateChildHealthPostnatalCareForms,
    AggregateChildHealthTHRForms,
    AggregateComplementaryFeedingForms,
    AggregateGrowthMonitoringForms,
    AwcLocation,
    AWWIncentiveReport,
    CcsRecordMonthly,
    ChildHealthMonthly,
    ICDSAuditEntryRecord,
    UcrTableNameMapping,
    IcdsMonths)
from custom.icds_reports.models.aggregate import (
    AggAwcDaily,
    AggregateBeneficiaryForm,
    AggregateInactiveAWW,
    AggregateLsAWCVisitForm,
    AggregateLsVhndForm,
    DailyAttendance,
    AggregateTHRForm
)
from custom.icds_reports.models.helper import IcdsFile
from custom.icds_reports.reports.disha import build_dumps_for_month
from custom.icds_reports.reports.incentive import IncentiveReport
from custom.icds_reports.reports.issnip_monthly_register import (
    ISSNIPMonthlyReport,
)
from custom.icds_reports.sqldata.exports.awc_infrastructure import (
    AWCInfrastructureExport,
)
from custom.icds_reports.sqldata.exports.beneficiary import BeneficiaryExport
from custom.icds_reports.sqldata.exports.children import ChildrenExport
from custom.icds_reports.sqldata.exports.demographics import DemographicsExport
from custom.icds_reports.sqldata.exports.lady_supervisor import (
    LadySupervisorExport,
)
from custom.icds_reports.reports.take_home_ration import (
    TakeHomeRationExport
)
from custom.icds_reports.sqldata.exports.pregnant_women import (
    PregnantWomenExport,
)
from custom.icds_reports.sqldata.exports.system_usage import SystemUsageExport
from custom.icds_reports.utils import (
    create_aww_performance_excel_file,
    create_excel_file,
    create_excel_file_in_openpyxl,
    create_lady_supervisor_excel_file,
    create_thr_report_excel_file,
    create_pdf_file,
    get_performance_report_blob_key,
    icds_pre_release_features,
    track_time,
    zip_folder,
)
from custom.icds_reports.utils.aggregation_helpers.helpers import get_helper
from custom.icds_reports.utils.aggregation_helpers.monolith import (
    ChildHealthMonthlyAggregationHelper,
)
from custom.icds_reports.utils.aggregation_helpers.monolith.mbt import (
    AwcMbtHelper,
    CcsMbtHelper,
    ChildHealthMbtHelper,
)
from six.moves import zip

celery_task_logger = logging.getLogger('celery.task')

UCRAggregationTask = namedtuple("UCRAggregationTask", ['type', 'date'])

DASHBOARD_TEAM_EMAILS = ['{}@{}'.format('dashboard-aggregation-script', 'dimagi.com')]
_dashboard_team_soft_assert = soft_assert(to=DASHBOARD_TEAM_EMAILS, send_to_ops=False)


UCR_TABLE_NAME_MAPPING = [
    {'type': "awc_location", 'name': 'static-awc_location'},
    {'type': 'daily_feeding', 'name': 'static-daily_feeding_forms'},
    {'type': 'household', 'name': 'static-household_cases'},
    {'type': 'infrastructure', 'name': 'static-infrastructure_form'},
    {'type': 'person', 'name': 'static-person_cases_v3'},
    {'type': 'usage', 'name': 'static-usage_forms'},
    {'type': 'vhnd', 'name': 'static-vhnd_form'},
    {'type': 'complementary_feeding', 'is_ucr': False, 'name': 'icds_dashboard_comp_feed_form'},
    {'type': 'aww_user', 'name': 'static-commcare_user_cases'},
    {'type': 'child_tasks', 'name': 'static-child_tasks_cases'},
    {'type': 'pregnant_tasks', 'name': 'static-pregnant-tasks_cases'},
    {'type': 'thr_form', 'is_ucr': False, 'name': 'icds_dashboard_child_health_thr_forms'},
    {'type': 'child_list', 'name': 'static-child_health_cases'},
    {'type': 'ccs_record_list', 'name': 'static-ccs_record_cases'},
    {'type': 'ls_vhnd', 'name': 'static-ls_vhnd_form'},
    {'type': 'ls_home_visits', 'name': 'static-ls_home_visit_forms_filled'},
    {'type': 'ls_awc_mgt', 'name': 'static-awc_mgt_forms'},
    {'type': 'cbe_form', 'name': 'static-cbe_form'},
    {'type': 'thr_form_v2', 'name': 'static-thr_forms_v2'}
]

SQL_FUNCTION_PATHS = [
    ('migrations', 'sql_templates', 'database_functions', 'update_months_table.sql'),
    ('migrations', 'sql_templates', 'database_functions', 'create_new_agg_table_for_month.sql'),
]


# Tasks that are only to be run on ICDS_ENVS should be marked
# with @only_icds_periodic_task rather than @periodic_task
if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
    only_icds_periodic_task = periodic_task
else:
    def only_icds_periodic_task(**kwargs):
        return lambda fn: fn


@periodic_task(run_every=crontab(minute=15, hour=18),
               acks_late=True, queue='icds_aggregation_queue')
def run_move_ucr_data_into_aggregation_tables_task():
    move_ucr_data_into_aggregation_tables.delay()


@periodic_task(run_every=crontab(minute=45, hour=17),
               acks_late=True, queue='icds_aggregation_queue')
def run_citus_move_ucr_data_into_aggregation_tables_task():
    if toggles.PARALLEL_AGGREGATION.enabled(DASHBOARD_DOMAIN):
        move_ucr_data_into_aggregation_tables.delay(force_citus=True)


@serial_task('{force_citus}', timeout=36 * 60 * 60, queue='icds_aggregation_queue')
def move_ucr_data_into_aggregation_tables(date=None, intervals=2, force_citus=False):
    if force_citus:
        force_citus_engine()

    start_time = datetime.now(pytz.utc)
    date = date or start_time.date()
    monthly_dates = []

    # probably this should be run one time, for now I leave this in aggregations script (not a big cost)
    # but remove issues when someone add new table to mapping, also we don't need to add new rows manually
    # on production servers
    _update_ucr_table_mapping()

    first_day_of_month = date.replace(day=1)
    for interval in range(intervals - 1, 0, -1):
        # calculate the last day of the previous months to send to the aggregation script
        first_day_next_month = first_day_of_month - relativedelta(months=interval - 1)
        monthly_dates.append(first_day_next_month - relativedelta(days=1))

    monthly_dates.append(date)

    db_alias = get_icds_ucr_db_alias_or_citus(force_citus)
    if db_alias:
        with connections[db_alias].cursor() as cursor:
            _create_aggregate_functions(cursor)

        _update_aggregate_locations_tables()

        state_ids = list(SQLLocation.objects
                     .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
                     .values_list('location_id', flat=True))

        for monthly_date in monthly_dates:
            calculation_date = monthly_date.strftime('%Y-%m-%d')
            res_daily = icds_aggregation_task.delay(date=calculation_date, func_name='_daily_attendance_table', force_citus=force_citus)
            res_daily.get(disable_sync_subtasks=False)

            stage_1_tasks = [
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_gm_forms', force_citus=force_citus)
                for state_id in state_ids
            ]
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_df_forms', force_citus=force_citus)
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_cf_forms', force_citus=force_citus)
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_ccs_cf_forms', force_citus=force_citus)
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_child_health_thr_forms', force_citus=force_citus)
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_ccs_record_thr_forms', force_citus=force_citus)
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_child_health_pnc_forms', force_citus=force_citus
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_ccs_record_pnc_forms', force_citus=force_citus
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_delivery_forms', force_citus=force_citus
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_bp_forms', force_citus=force_citus
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_awc_infra_forms', force_citus=force_citus)
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=calculation_date,
                                               func_name='_agg_thr_table', force_citus=force_citus)
                for state_id in state_ids
            ])

            stage_1_tasks.append(icds_aggregation_task.si(date=calculation_date, func_name='_update_months_table', force_citus=force_citus))

            # https://github.com/celery/celery/issues/4274
            stage_1_task_results = [stage_1_task.delay() for stage_1_task in stage_1_tasks]
            for stage_1_task_result in stage_1_task_results:
                stage_1_task_result.get(disable_sync_subtasks=False)

            res_child = chain(
                icds_state_aggregation_task.si(
                    state_id=state_ids, date=calculation_date, func_name='_child_health_monthly_table', force_citus=force_citus
                ),
                icds_aggregation_task.si(date=calculation_date, func_name='_agg_child_health_table', force_citus=force_citus)
            ).apply_async()
            res_ccs = chain(
                icds_aggregation_task.si(date=calculation_date, func_name='_ccs_record_monthly_table', force_citus=force_citus),
                icds_aggregation_task.si(date=calculation_date, func_name='_agg_ccs_record_table', force_citus=force_citus),
            ).apply_async()

            res_ccs.get(disable_sync_subtasks=False)
            res_child.get(disable_sync_subtasks=False)

            res_ls_tasks = list()
            res_ls_tasks.extend([icds_state_aggregation_task.si(state_id=state_id, date=calculation_date,
                                                                func_name='_agg_ls_awc_mgt_form', force_citus=force_citus)
                                 for state_id in state_ids
                                 ])
            res_ls_tasks.extend([icds_state_aggregation_task.si(state_id=state_id, date=calculation_date,
                                                                func_name='_agg_ls_vhnd_form', force_citus=force_citus)
                                 for state_id in state_ids
                                 ])
            res_ls_tasks.extend([icds_state_aggregation_task.si(state_id=state_id, date=calculation_date,
                                                                func_name='_agg_beneficiary_form', force_citus=force_citus)
                                 for state_id in state_ids
                                 ])

            res_ls_tasks.append(icds_aggregation_task.si(date=calculation_date, func_name='_agg_ls_table', force_citus=force_citus))

            res_awc = chain(icds_aggregation_task.si(date=calculation_date, func_name='_agg_awc_table', force_citus=force_citus),
                            *res_ls_tasks
                            ).apply_async()

            res_awc.get(disable_sync_subtasks=False)

            first_of_month_string = monthly_date.strftime('%Y-%m-01')
            for state_id in state_ids:
                create_mbt_for_month.delay(state_id, first_of_month_string, force_citus)
        if date.weekday() == 5:
            icds_aggregation_task.delay(date=date.strftime('%Y-%m-%d'), func_name='_agg_awc_table_weekly', force_citus=force_citus)
        chain(
            icds_aggregation_task.si(date=date.strftime('%Y-%m-%d'), func_name='aggregate_awc_daily',
                                     force_citus=force_citus),
            email_dashboad_team.si(aggregation_date=date.strftime('%Y-%m-%d'), aggregation_start_time=start_time,
                                   force_citus=force_citus)
        ).delay()


def _create_aggregate_functions(cursor):
    try:
        celery_task_logger.info("Starting icds reports create_functions")
        for sql_function_path in SQL_FUNCTION_PATHS:
            path = os.path.join(os.path.dirname(__file__), *sql_function_path)
            with open(path, "r", encoding='utf-8') as sql_file:
                sql_to_execute = sql_file.read()
                cursor.execute(sql_to_execute)
        celery_task_logger.info("Ended icds reports create_functions")
    except Exception:
        # This is likely due to a change in the UCR models or aggregation script which should be rare
        # First step would be to look through this error to find what function is causing the error
        # and look for recent changes in this folder.
        _dashboard_team_soft_assert(False, "Unexpected occurred while creating functions in dashboard aggregation")
        raise


def _update_aggregate_locations_tables():
    try:
        celery_task_logger.info("Starting icds reports update_location_tables")
        with transaction.atomic(using=db_for_read_write(AwcLocation)):
            AwcLocation.aggregate()
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


@task(serializer='pickle', queue='icds_aggregation_queue', bind=True, default_retry_delay=15 * 60, acks_late=True)
def icds_aggregation_task(self, date, func_name, force_citus=False):
    if force_citus:
        force_citus_engine()
    func = {
        '_agg_ls_table': _agg_ls_table,
        '_update_months_table': _update_months_table,
        '_daily_attendance_table': _daily_attendance_table,
        '_agg_child_health_table': _agg_child_health_table,
        '_ccs_record_monthly_table': _ccs_record_monthly_table,
        '_agg_ccs_record_table': _agg_ccs_record_table,
        '_agg_awc_table': _agg_awc_table,
        '_agg_awc_table_weekly': _agg_awc_table_weekly,
        'aggregate_awc_daily': aggregate_awc_daily,
    }[func_name]

    if six.PY2 and isinstance(date, bytes):
        date = date.decode('utf-8')

    db_alias = get_icds_ucr_db_alias_or_citus(force_citus)
    if not db_alias:
        return

    celery_task_logger.info("Starting icds reports {} {}".format(date, func.__name__))
    try:
        func(date)
    except Error as exc:
        notify_exception(
            None, message="Error occurred during ICDS aggregation",
            details={'func': func.__name__, 'date': date, 'error': exc}
        )
        _dashboard_team_soft_assert(
            False,
            "{}{} aggregation failed on {} for {}. This task will be retried in 15 minutes".format(
                'Citus' if force_citus else '', func.__name__, settings.SERVER_ENVIRONMENT, date
            )
        )
        self.retry(exc=exc)

    celery_task_logger.info("Ended icds reports {} {}".format(date, func.__name__))


@task(serializer='pickle', queue='icds_aggregation_queue', bind=True, default_retry_delay=15 * 60, acks_late=True)
def icds_state_aggregation_task(self, state_id, date, func_name, force_citus=False):
    if force_citus:
        force_citus_engine()
    func = {
        '_aggregate_gm_forms': _aggregate_gm_forms,
        '_aggregate_df_forms': _aggregate_df_forms,
        '_aggregate_cf_forms': _aggregate_cf_forms,
        '_aggregate_ccs_cf_forms': _aggregate_ccs_cf_forms,
        '_aggregate_child_health_thr_forms': _aggregate_child_health_thr_forms,
        '_aggregate_ccs_record_thr_forms': _aggregate_ccs_record_thr_forms,
        '_aggregate_child_health_pnc_forms': _aggregate_child_health_pnc_forms,
        '_aggregate_ccs_record_pnc_forms': _aggregate_ccs_record_pnc_forms,
        '_aggregate_delivery_forms': _aggregate_delivery_forms,
        '_aggregate_bp_forms': _aggregate_bp_forms,
        '_aggregate_awc_infra_forms': _aggregate_awc_infra_forms,
        '_child_health_monthly_table': _child_health_monthly_table,
        '_agg_ls_awc_mgt_form': _agg_ls_awc_mgt_form,
        '_agg_ls_vhnd_form': _agg_ls_vhnd_form,
        '_agg_beneficiary_form': _agg_beneficiary_form,
        '_agg_thr_table': _agg_thr_table
    }[func_name]

    if six.PY2 and isinstance(date, bytes):
        date = date.decode('utf-8')

    db_alias = get_icds_ucr_db_alias_or_citus(force_citus)
    if not db_alias:
        return

    celery_task_logger.info("Starting icds reports {} {} {}".format(state_id, date, func.__name__))

    try:
        func(state_id, date)
    except Error as exc:
        notify_exception(
            None, message="Error occurred during ICDS aggregation",
            details={'func': func.__name__, 'date': date, 'state_id': state_id, 'error': exc}
        )
        citus = 'Citus ' if force_citus else ''
        _dashboard_team_soft_assert(
            False,
            "{}{} aggregation failed on {} for {} on {}. This task will be retried in 15 minutes".format(
                citus, func.__name__, settings.SERVER_ENVIRONMENT, state_id, date
            )
        )
        self.retry(exc=exc)

    celery_task_logger.info("Ended icds reports {} {} {}".format(state_id, date, func.__name__))


@track_time
def _aggregate_cf_forms(state_id, day):
    AggregateComplementaryFeedingForms.aggregate(state_id, day)


@track_time
def _aggregate_ccs_cf_forms(state_id, day):
    AggregateCcsRecordComplementaryFeedingForms.aggregate(state_id, day)


@track_time
def _aggregate_gm_forms(state_id, day):
    AggregateGrowthMonitoringForms.aggregate(state_id, day)


@track_time
def _aggregate_df_forms(state_id, day):
    AggregateChildHealthDailyFeedingForms.aggregate(state_id, day)


@track_time
def _aggregate_child_health_pnc_forms(state_id, day):
    AggregateChildHealthPostnatalCareForms.aggregate(state_id, day)


@track_time
def _aggregate_ccs_record_pnc_forms(state_id, day):
    AggregateCcsRecordPostnatalCareForms.aggregate(state_id, day)


@track_time
def _aggregate_child_health_thr_forms(state_id, day):
    AggregateChildHealthTHRForms.aggregate(state_id, day)


@track_time
def _aggregate_ccs_record_thr_forms(state_id, day):
    AggregateCcsRecordTHRForms.aggregate(state_id, day)


@track_time
def _aggregate_awc_infra_forms(state_id, day):
    AggregateAwcInfrastructureForms.aggregate(state_id, day)


@task(serializer='pickle', queue='icds_aggregation_queue', default_retry_delay=15 * 60, acks_late=True)
@track_time
def _aggregate_inactive_aww(day, force_citus=False):
    if force_citus:
        force_citus_engine()
    AggregateInactiveAWW.aggregate(day)


@track_time
def _aggregate_delivery_forms(state_id, day):
    AggregateCcsRecordDeliveryForms.aggregate(state_id, day)


@track_time
def _aggregate_bp_forms(state_id, day):
    AggregateBirthPreparednesForms.aggregate(state_id, day)


def _run_custom_sql_script(commands, day=None, db_alias=None):
    if not db_alias:
        return

    with transaction.atomic(using=db_alias):
        with connections[db_alias].cursor() as cursor:
            for command in commands:
                cursor.execute(command, [day])


@track_time
def aggregate_awc_daily(day):
    with transaction.atomic(using=db_for_read_write(AggAwcDaily)):
        AggAwcDaily.aggregate(force_to_date(day))


@track_time
def _update_months_table(day):
    db_alias = db_for_read_write(IcdsMonths)
    _run_custom_sql_script(["SELECT update_months_table(%s)"], day, db_alias=db_alias)


def get_cursor(model, write=True):
    db = db_for_read_write(model, write)
    return connections[db].cursor()


@track_time
def _child_health_monthly_table(state_ids, day):
    force_citus = forced_citus()
    helper = get_helper(ChildHealthMonthlyAggregationHelper.helper_key)(state_ids, force_to_date(day))

    celery_task_logger.info("Creating temporary table")
    with get_cursor(ChildHealthMonthly) as cursor:
        cursor.execute(helper.drop_temporary_table())
        cursor.execute(helper.create_temporary_table())

    # https://github.com/celery/celery/issues/4274
    sub_aggregations = [
        _child_health_helper.delay(query=query, params=params, force_citus=force_citus)
        for query, params in helper.pre_aggregation_queries()
    ]
    for sub_aggregation in sub_aggregations:
        sub_aggregation.get(disable_sync_subtasks=False)

    celery_task_logger.info("Inserting into child_health_monthly_table")
    with transaction.atomic(using=db_for_read_write(ChildHealthMonthly)):
        ChildHealthMonthly.aggregate(state_ids, force_to_date(day))

    celery_task_logger.info("Dropping temporary table")
    with get_cursor(ChildHealthMonthly) as cursor:
        cursor.execute(helper.drop_temporary_table())


@task(serializer='pickle', queue='icds_aggregation_queue', default_retry_delay=15 * 60, acks_late=True)
@track_time
def _child_health_helper(query, params, force_citus=False):
    if force_citus:
        force_citus_engine()
    celery_task_logger.info("Running child_health_helper with %s", params)
    with get_cursor(ChildHealthMonthly) as cursor:
        cursor.execute(query, params)


@track_time
def _ccs_record_monthly_table(day):
    with transaction.atomic(using=db_for_read_write(CcsRecordMonthly)):
        CcsRecordMonthly.aggregate(force_to_date(day))


@track_time
def _daily_attendance_table(day):
    DailyAttendance.aggregate(force_to_date(day))


@track_time
def _agg_child_health_table(day):
    db_alias = db_for_read_write(AggChildHealth)
    with transaction.atomic(using=db_alias):
        _run_custom_sql_script([
            "SELECT create_new_aggregate_table_for_month('agg_child_health', %s)",
        ], day, db_alias=db_alias)
        AggChildHealth.aggregate(force_to_date(day))


@track_time
def _agg_ccs_record_table(day):
    db_alias = db_for_read_write(AggCcsRecord)
    with transaction.atomic(using=db_alias):
        _run_custom_sql_script([
            "SELECT create_new_aggregate_table_for_month('agg_ccs_record', %s)",
        ], day, db_alias=db_alias)
        AggCcsRecord.aggregate(force_to_date(day))


@track_time
def _agg_awc_table(day):
    db_alias = db_for_read_write(AggAwc)
    with transaction.atomic(using=db_alias):
        _run_custom_sql_script([
            "SELECT create_new_aggregate_table_for_month('agg_awc', %s)"
        ], day, db_alias=db_alias)
        AggAwc.aggregate(force_to_date(day))


@track_time
def _agg_ls_vhnd_form(state_id, day):
    with transaction.atomic(using=db_for_read_write(AggLs)):
        AggregateLsVhndForm.aggregate(state_id, force_to_date(day))


@track_time
def _agg_beneficiary_form(state_id, day):
    with transaction.atomic(using=db_for_read_write(AggLs)):
        AggregateBeneficiaryForm.aggregate(state_id, force_to_date(day))


@track_time
def _agg_ls_awc_mgt_form(state_id, day):
    with transaction.atomic(using=db_for_read_write(AggLs)):
        AggregateLsAWCVisitForm.aggregate(state_id, force_to_date(day))


@track_time
def _agg_ls_table(day):
    with transaction.atomic(using=db_for_read_write(AggLs)):
        AggLs.aggregate(force_to_date(day))


@track_time
def _agg_thr_table(state_id, day):
    with transaction.atomic(using=db_for_read_write(AggregateTHRForm)):
        AggregateTHRForm.aggregate(state_id, force_to_date(day))


@track_time
def _agg_awc_table_weekly(day):
    with transaction.atomic(using=db_for_read_write(AggAwc)):
        AggAwc.weekly_aggregate(force_to_date(day))


@task(serializer='pickle', queue='icds_aggregation_queue')
def email_dashboad_team(aggregation_date, aggregation_start_time, force_citus=False):
    aggregation_start_time = aggregation_start_time.astimezone(INDIA_TIMEZONE)
    aggregation_finish_time = datetime.now(INDIA_TIMEZONE)
    if six.PY2 and isinstance(aggregation_date, bytes):
        aggregation_date = aggregation_date.decode('utf-8')

    # temporary soft assert to verify it's completing
    if not settings.UNIT_TESTING:
        citus = 'Citus ' if force_citus else ''
        timings = "Aggregation Started At : {} IST, Completed At : {} IST".format(aggregation_start_time,
                                                                                  aggregation_finish_time)
        _dashboard_team_soft_assert(False, "{}Aggregation completed on {}".format(citus,
                                                                                  settings.SERVER_ENVIRONMENT),
                                    timings)
    celery_task_logger.info("Aggregation has completed")
    icds_data_validation.delay(aggregation_date)


@periodic_task(
    queue='background_queue',
    run_every=crontab(day_of_week='tuesday,thursday,saturday', minute=0, hour=16),
    acks_late=True
)
def recalculate_stagnant_cases():
    domain = 'icds-cas'
    config_ids = [
        'static-icds-cas-static-ccs_record_cases_monthly_v2',
        'static-icds-cas-static-child_cases_monthly_v2',
    ]

    track_case_load = case_load_counter("find_stagnant_cases", domain)
    stagnant_cases = set()
    for config_id in config_ids:
        config, is_static = get_datasource_config(config_id, domain)
        adapter = get_indicator_adapter(config, load_source='find_stagnant_cases')
        case_ids = _find_stagnant_cases(adapter)
        num_cases = len(case_ids)
        adapter.track_load(num_cases)
        celery_task_logger.info(
            "Found {} stagnant cases in config {}".format(num_cases, config_id)
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
            track_case_load()
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


@task(serializer='pickle', queue='icds_dashboard_reports_queue')
def prepare_excel_reports(config, aggregation_level, include_test, beta, location, domain,
                          file_format, indicator):
    if indicator == CHILDREN_EXPORT:
        data_type = 'Children'
        excel_data = ChildrenExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta
        ).get_excel_data(location)
    elif indicator == PREGNANT_WOMEN_EXPORT:
        data_type = 'Pregnant_Women'
        excel_data = PregnantWomenExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test
        ).get_excel_data(location)
    elif indicator == DEMOGRAPHICS_EXPORT:
        data_type = 'Demographics'
        excel_data = DemographicsExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta
        ).get_excel_data(location)
    elif indicator == SYSTEM_USAGE_EXPORT:
        data_type = 'System_Usage'
        excel_data = SystemUsageExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test
        ).get_excel_data(
            location,
            system_usage_num_launched_awcs_formatting_at_awc_level=aggregation_level > 4 and beta,
            system_usage_num_of_days_awc_was_open_formatting=aggregation_level <= 4 and beta,
        )
    elif indicator == AWC_INFRASTRUCTURE_EXPORT:
        data_type = 'AWC_Infrastructure'
        excel_data = AWCInfrastructureExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta,
        ).get_excel_data(location)
    elif indicator == BENEFICIARY_LIST_EXPORT:
        # this report doesn't use this configuration
        config.pop('aggregation_level', None)
        data_type = 'Beneficiary_List'
        excel_data = BeneficiaryExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta
        ).get_excel_data(location)
    elif indicator == AWW_INCENTIVE_REPORT:
        today = date.today()
        data_type = 'AWW_Performance_{}'.format(today.strftime('%Y_%m_%d'))
        month = config['month'].strftime("%B %Y")
        state = SQLLocation.objects.get(
            location_id=config['state_id'], domain=config['domain']
        ).name
        district = SQLLocation.objects.get(
            location_id=config['district_id'], domain=config['domain']
        ).name if aggregation_level >= 2 else None
        block = SQLLocation.objects.get(
            location_id=config['block_id'], domain=config['domain']
        ).name if aggregation_level == 3 else None
        cache_key = get_performance_report_blob_key(state, district, block, month, file_format)
    elif indicator == LS_REPORT_EXPORT:
        data_type = 'Lady_Supervisor'
        config['aggregation_level'] = 4  # this report on all levels shows data (row) per sector
        excel_data = LadySupervisorExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta
        ).get_excel_data(location)
        if file_format == 'xlsx':
            cache_key = create_lady_supervisor_excel_file(
                excel_data,
                data_type,
                config['month'].strftime("%B %Y"),
                aggregation_level,
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)
    elif indicator == THR_REPORT_EXPORT:
        loc_level = aggregation_level if location else 0
        excel_data = TakeHomeRationExport(
            location=location,
            month=config['month'],
            loc_level=loc_level,
            beta=beta
        ).get_excel_data()
        export_info = excel_data[1][1]
        generated_timestamp = date_parser.parse(export_info[0][1])
        formatted_timestamp = generated_timestamp.strftime("%d-%m-%Y__%H-%M-%S")
        data_type = 'THR Report__{}'.format(formatted_timestamp)

        if file_format == 'xlsx':
            cache_key = create_thr_report_excel_file(
                excel_data,
                data_type,
                config['month'].strftime("%B %Y"),
                loc_level,
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)

    if indicator not in (AWW_INCENTIVE_REPORT, LS_REPORT_EXPORT, THR_REPORT_EXPORT):
        if file_format == 'xlsx' and beta:
            cache_key = create_excel_file_in_openpyxl(excel_data, data_type)
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)
    params = {
        'domain': domain,
        'uuid': cache_key,
        'file_format': file_format,
        'data_type': data_type,
    }
    return {
        'domain': domain,
        'uuid': cache_key,
        'file_format': file_format,
        'data_type': data_type,
        'link': reverse('icds_download_excel', params=params, absolute=True, kwargs={'domain': domain})
    }


@task(serializer='pickle', queue='icds_dashboard_reports_queue')
def prepare_issnip_monthly_register_reports(domain, awcs, pdf_format, month, year, couch_user):
    selected_date = date(year, month, 1)
    report_context = {
        'reports': [],
        'user_have_access_to_features': icds_pre_release_features(couch_user),
    }

    pdf_files = {}

    report_data = ISSNIPMonthlyReport(config={
        'awc_id': awcs,
        'month': selected_date,
        'domain': domain
    }, icds_feature_flag=icds_pre_release_features(couch_user)).to_pdf_format

    if pdf_format == 'one':
        report_context['reports'] = report_data
        cache_key = create_pdf_file(report_context)
    else:
        for data in report_data:
            report_context['reports'] = [data]
            pdf_hash = create_pdf_file(report_context)
            pdf_files.update({
                pdf_hash: data['awc_name']
            })
        cache_key = zip_folder(pdf_files)

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


@task(serializer='pickle', queue='background_queue')
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

    bad_lbw_awcs = AggChildHealthMonthly.objects.filter(
        month=month, aggregation_level=5, weighed_and_born_in_month__lt=F('low_birth_weight_in_month')
    ).values_list(*return_values)

    _send_data_validation_email(
        return_values, month, {
            'bad_wasting_awcs': bad_wasting_awcs,
            'bad_stunting_awcs': bad_stunting_awcs,
            'bad_underweight_awcs': bad_underweight_awcs,
            'bad_lbw_awcs': bad_lbw_awcs,
        })


def _send_data_validation_email(csv_columns, month, bad_data):
    # intentionally using length here because the query will need to evaluate anyway to send the CSV file
    if all(len(v) == 0 for _, v in six.iteritems(bad_data)):
        return

    bad_wasting_awcs = bad_data.get('bad_wasting_awcs', [])
    bad_stunting_awcs = bad_data.get('bad_stunting_awcs', [])
    bad_underweight_awcs = bad_data.get('bad_underweight_awcs', [])
    bad_lbw_awcs = bad_data.get('bad_lbw_awcs', [])

    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerow(('type',) + csv_columns)
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
        '[{}] - ICDS Dashboard Validation Results'.format(settings.SERVER_ENVIRONMENT),
        DASHBOARD_TEAM_EMAILS, email_content,
        file_attachments=[{'file_obj': csv_file, 'title': filename, 'mimetype': 'text/csv'}],
    )


def _icds_add_awcs_to_file(csv_writer, error_type, rows):
    for row in rows:
        csv_writer.writerow((error_type, ) + row)


def _update_ucr_table_mapping():
    celery_task_logger.info("Started updating ucr_table_name_mapping table")
    for table in UCR_TABLE_NAME_MAPPING:
        if table.get('is_ucr', True):
            table_name = get_table_name(DASHBOARD_DOMAIN, table['name'])
        else:
            table_name = table['name']
        UcrTableNameMapping.objects.update_or_create(
            table_type=table['type'],
            defaults={'table_name': table_name}
        )
    celery_task_logger.info("Ended updating ucr_table_name_mapping table")


def _get_value(data, field):
    default = 'N/A'
    if field == 'days_inactive':
        default = 0
    return getattr(data, field) or default


# This task caused memory spikes once a day on the india env
# before it was switched to icds-only (June 2019)
@only_icds_periodic_task(run_every=crontab(minute=30, hour=18), acks_late=True, queue='icds_aggregation_queue')
def collect_inactive_awws():
    celery_task_logger.info("Started updating the Inactive AWW")
    filename = "inactive_awws_%s.csv" % date.today().strftime('%Y-%m-%d')
    last_sync = IcdsFile.objects.filter(data_type='inactive_awws').order_by('-file_added').first()

    # If last sync not exist then collect initial data
    if not last_sync:
        last_sync_date = datetime(2017, 3, 1).date()
    else:
        last_sync_date = last_sync.file_added

    _aggregate_inactive_aww(last_sync_date)
    if toggles.PARALLEL_AGGREGATION.enabled(DASHBOARD_DOMAIN):
        _aggregate_inactive_aww.delay(last_sync_date, force_citus=True)

    celery_task_logger.info("Collecting inactive AWW to generate zip file")
    excel_data = AggregateInactiveAWW.objects.all()

    celery_task_logger.info("Preparing data to csv file")
    columns = [x.name for x in AggregateInactiveAWW._meta.fields] + [
        'days_since_start',
        'days_inactive'
    ]
    rows = [columns]
    for data in excel_data:
        rows.append(
            [_get_value(data, field) for field in columns]
        )

    celery_task_logger.info("Creating csv file")
    export_file = BytesIO()
    export_from_tables([['inactive AWWSs', rows]], export_file, 'csv')

    celery_task_logger.info("Saving csv file in blobdb")
    sync = IcdsFile(blob_id=filename, data_type='inactive_awws')
    sync.store_file_in_blobdb(export_file)
    sync.save()
    celery_task_logger.info("Ended updating the Inactive AWW")


@periodic_task(run_every=crontab(day_of_week='monday', hour=0, minute=0),
               acks_late=True, queue='background_queue')
def collect_inactive_dashboard_users():
    celery_task_logger.info("Started updating the Inactive Dashboard users")

    end_date = datetime.utcnow()
    start_date_week = end_date - timedelta(days=7)
    start_date_month = end_date - timedelta(days=30)

    not_logged_in_week = get_dashboard_users_not_logged_in(start_date_week, end_date)
    not_logged_in_month = get_dashboard_users_not_logged_in(start_date_month, end_date)

    week_file_name = 'dashboard_users_not_logged_in_{:%Y-%m-%d}_to_{:%Y-%m-%d}.csv'.format(
        start_date_week, end_date
    )
    month_file_name = 'dashboard_users_not_logged_in_{:%Y-%m-%d}_to_{:%Y-%m-%d}.csv'.format(
        start_date_month, end_date
    )
    rows_not_logged_in_week = _get_inactive_dashboard_user_rows(not_logged_in_week)
    rows_not_logged_in_month = _get_inactive_dashboard_user_rows(not_logged_in_month)

    sync = IcdsFile(blob_id="inactive_dashboad_users_%s.zip" % date.today().strftime('%Y-%m-%d'),
                    data_type='inactive_dashboard_users')

    in_memory = BytesIO()
    zip_file = zipfile.ZipFile(in_memory, 'w', zipfile.ZIP_DEFLATED)

    zip_file.writestr(week_file_name,
                      '\n'.join(rows_not_logged_in_week)
                      )
    zip_file.writestr(month_file_name,
                      '\n'.join(rows_not_logged_in_month)
                      )

    zip_file.close()

    # we need to reset buffer position to the beginning after creating zip, if not read() will return empty string
    # we read this to save file in blobdb
    in_memory.seek(0)
    sync.store_file_in_blobdb(in_memory)

    sync.save()


def _get_inactive_dashboard_user_rows(not_logged_in_week):
    from corehq.apps.users.models import CommCareUser
    rows = ['"Username","Location","State"']
    for username in not_logged_in_week:
        user = CommCareUser.get_by_username(username)
        loc = user.sql_location
        loc_name = loc.name.encode('ascii', 'replace').decode() if loc else ''
        state = loc.get_ancestor_of_type('state') if loc else None
        state_name = state.name.encode('ascii', 'replace').decode() if state else ''
        rows.append('"{}","{}","{}"'.format(username, loc_name, state_name))

    return rows


def get_dashboard_users_not_logged_in(start_date, end_date, domain='icds-cas'):

    all_users = get_all_user_id_username_pairs_by_domain(domain, include_web_users=False,
                                                         include_mobile_users=True)

    dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')
    dashboard_usernames = {
        uname
        for id, uname in all_users
        if dashboard_uname_rx.match(uname)
    }

    logged_in = ICDSAuditEntryRecord.objects.filter(
        time_of_use__gte=start_date, time_of_use__lt=end_date
    ).values_list('username', flat=True)

    logged_in_dashboard_users = {
        u
        for u in logged_in
        if dashboard_uname_rx.match(u)
    }

    not_logged_in = dashboard_usernames - logged_in_dashboard_users
    return not_logged_in


@periodic_task(run_every=crontab(day_of_week=5, hour=14, minute=0), acks_late=True, queue='icds_aggregation_queue')
def build_disha_dump():
    # Weekly refresh of disha dumps for current and last month
    DISHA_NOTIFICATION_EMAIL = '{}@{}'.format('icds-dashboard', 'dimagi.com')
    _soft_assert = soft_assert(to=[DISHA_NOTIFICATION_EMAIL], send_to_ops=False)
    month = date.today().replace(day=1)
    last_month = month - timedelta(days=1)
    last_month = last_month.replace(day=1)
    celery_task_logger.info("Started dumping DISHA data")
    try:
        build_dumps_for_month(month, rebuild=True)
        build_dumps_for_month(last_month, rebuild=True)
    except Exception:
        _soft_assert(False, "DISHA weekly task has failed.")
    else:
        _soft_assert(False, "DISHA weekly task has succeeded.")
    celery_task_logger.info("Finished dumping DISHA data")


@periodic_task(run_every=crontab(hour=17, minute=0, day_of_month='12'), acks_late=True, queue='icds_aggregation_queue')
def build_incentive_report(agg_date=None):
    state_ids = (SQLLocation.objects
                 .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
                 .values_list('location_id', flat=True))
    locations = (SQLLocation.objects
                 .filter(domain=DASHBOARD_DOMAIN, location_type__name__in=['state', 'district', 'block'])
                 .select_related('parent__parent', 'location_type'))
    if agg_date is None:
        current_month = date.today().replace(day=1)
        agg_date = current_month - relativedelta(months=1)
    for state in state_ids:
        AWWIncentiveReport.aggregate(state, agg_date)
    for file_format in ['xlsx', 'csv']:
        for location in locations:
            if location.location_type.name == 'state':
                build_incentive_files.delay(location, agg_date, file_format, 1, location)
            elif location.location_type.name == 'district':
                build_incentive_files.delay(location, agg_date, file_format, 2, location.parent, location)
            else:
                build_incentive_files.delay(location, agg_date, file_format, 3, location.parent.parent, location.parent)


@task(queue='icds_dashboard_reports_queue', serializer='pickle')
def build_incentive_files(location, month, file_format, aggregation_level, state, district=None):
    data_type = 'AWW_Performance'
    excel_data = IncentiveReport(
        location=location.location_id,
        month=month,
        aggregation_level=aggregation_level
    ).get_excel_data()
    state_name = state.name
    district_name = district.name if aggregation_level >= 2 else None
    block_name = location.name if aggregation_level == 3 else None
    month_string = month.strftime("%B %Y")
    if file_format == 'xlsx':
        create_aww_performance_excel_file(
            excel_data,
            data_type,
            month_string,
            state_name,
            district_name,
            block_name
        )
    else:
        blob_key = get_performance_report_blob_key(state_name, district_name, block_name, month_string, file_format)
        create_excel_file(excel_data, data_type, file_format, blob_key, timeout=None)


@task(queue='icds_dashboard_reports_queue')
def create_mbt_for_month(state_id, month, force_citus=False):
    if force_citus:
        force_citus_engine()
    helpers = (CcsMbtHelper, ChildHealthMbtHelper, AwcMbtHelper)
    for helper_class in helpers:
        helper = get_helper(helper_class.helper_key)(state_id, month)
        # run on primary DB to avoid "conflict with recovery" errors
        with get_cursor(helper.base_class, write=True) as cursor, tempfile.TemporaryFile() as f:
            cursor.copy_expert(helper.query(), f)
            f.seek(0)
            icds_file, _ = IcdsFile.objects.get_or_create(
                blob_id='{}-{}-{}'.format(helper.base_tablename, state_id, month),
                data_type='mbt_{}'.format(helper.base_tablename)
            )
            icds_file.store_file_in_blobdb(f, expired=THREE_MONTHS)
            icds_file.save()


@task(queue='dashboard_comparison_queue')
def run_citus_experiment_raw_sql(parameterized_sql, params, data_source="Unknown"):
    experiment_context = {
        "data_source": data_source,
        "sql_query": parameterized_sql,
        "params": params,
    }
    experiment = DashboardQueryExperiment(name="Dashboard Query Experiment", context=experiment_context)
    with experiment.control() as control:
        db_alias = get_icds_ucr_db_alias()
        with connections[db_alias].cursor() as cursor:
            cursor.execute(parameterized_sql, params)
            control.record(_dictfetchall(cursor))

    with experiment.candidate() as candidate:
        db_alias = get_icds_ucr_citus_db_alias()
        with connections[db_alias].cursor() as cursor:
            cursor.execute(parameterized_sql, params)
            candidate.record(_dictfetchall(cursor))

    objects = experiment.run()
    return objects


def _dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
