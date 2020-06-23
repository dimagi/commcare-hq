import csv
import io
import logging
import os
import re
import tempfile
import zipfile
from collections import namedtuple
from datetime import date, datetime, timedelta
from io import BytesIO, open

from django.conf import settings
from django.db import Error, IntegrityError, connections, transaction, router
from django.db.models import F

import pytz
from celery import chain
from celery.schedules import crontab
from celery.task import task
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from gevent.pool import Pool

from couchexport.export import export_from_tables
from couchexport.models import Format
from dimagi.utils.chunked import chunked
from dimagi.utils.dates import force_to_date, force_to_datetime
from dimagi.utils.logging import notify_exception
from pillowtop.feed.interface import ChangeMeta

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.reports.analytics.esaccessors import (
    get_case_ids_missing_from_elasticsearch,
    get_form_ids_missing_from_elasticsearch)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import (
    AsyncIndicator,
    InvalidUCRData,
    get_datasource_config,
)
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_user_id_username_pairs_by_domain,
)
from corehq.const import SERVER_DATE_FORMAT, SERVER_DATETIME_FORMAT
from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from corehq.util.celery_utils import periodic_task_on_envs
from corehq.util.decorators import serial_task
from corehq.util.log import send_HTML_email
from corehq.util.metrics import metrics_counter
from corehq.util.soft_assert import soft_assert
from corehq.util.view_utils import reverse
from custom.icds_reports.const import (
    AWC_INFRASTRUCTURE_EXPORT,
    AWW_INCENTIVE_REPORT,
    CHILDREN_EXPORT,
    DASHBOARD_DOMAIN,
    DEMOGRAPHICS_EXPORT,
    GROWTH_MONITORING_LIST_EXPORT,
    INDIA_TIMEZONE,
    LS_REPORT_EXPORT,
    PREGNANT_WOMEN_EXPORT,
    SYSTEM_USAGE_EXPORT,
    THR_REPORT_EXPORT,
    THREE_MONTHS,
    DASHBOARD_USAGE_EXPORT,
    SERVICE_DELIVERY_REPORT,
    CHILD_GROWTH_TRACKER_REPORT,
    POSHAN_PROGRESS_REPORT,
    AWW_ACTIVITY_REPORT
)
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
    IcdsMonths,
    UcrTableNameMapping,
)
from custom.icds_reports.models.aggregate import (
    AggAwcDaily,
    AggregateBeneficiaryForm,
    AggregateInactiveAWW,
    AggregateLsAWCVisitForm,
    AggregateLsVhndForm,
    AggregateTHRForm,
    DailyAttendance,
    DashboardUserActivityReport,
    AggregateAdolescentGirlsRegistrationForms,
    AggGovernanceDashboard,
    AggServiceDeliveryReport,
    AggregateMigrationForms,
    AggregateAvailingServiceForms,
    BiharAPIDemographics,
    ChildVaccines

)
from custom.icds_reports.models.helper import IcdsFile
from custom.icds_reports.models.util import UcrReconciliationStatus
from custom.icds_reports.reports.disha import DishaDump, build_dumps_for_month
from custom.icds_reports.reports.incentive import IncentiveReport
from custom.icds_reports.reports.issnip_monthly_register import (
    ISSNIPMonthlyReport,
)
from custom.icds_reports.reports.take_home_ration import TakeHomeRationExport
from custom.icds_reports.reports.service_delivery_report import ServiceDeliveryReport
from custom.icds_reports.sqldata.exports.awc_infrastructure import (
    AWCInfrastructureExport,
)
from custom.icds_reports.sqldata.exports.aww_activity_report import AwwActivityExport
from custom.icds_reports.sqldata.exports.beneficiary import BeneficiaryExport
from custom.icds_reports.sqldata.exports.children import ChildrenExport
from custom.icds_reports.sqldata.exports.dashboard_usage import DashBoardUsage
from custom.icds_reports.sqldata.exports.demographics import DemographicsExport
from custom.icds_reports.sqldata.exports.growth_tracker_report import GrowthTrackerExport
from custom.icds_reports.sqldata.exports.lady_supervisor import (
    LadySupervisorExport,
)
from custom.icds_reports.sqldata.exports.poshan_progress_report import PoshanProgressReport
from custom.icds_reports.sqldata.exports.pregnant_women import (
    PregnantWomenExport,
)
from custom.icds_reports.sqldata.exports.system_usage import SystemUsageExport
from custom.icds_reports.utils import (
    create_aww_performance_excel_file,
    create_child_report_excel_file,
    create_excel_file,
    create_excel_file_in_openpyxl,
    create_lady_supervisor_excel_file,
    create_pdf_file,
    create_thr_report_excel_file,
    get_performance_report_blob_key,
    icds_pre_release_features,
    track_time,
    zip_folder,
    get_dashboard_usage_excel_file,
    create_service_delivery_report,
    create_child_growth_tracker_report,
    create_poshan_progress_report,
    create_aww_activity_report
)
from custom.icds_reports.utils.aggregation_helpers.distributed import (
    ChildHealthMonthlyAggregationDistributedHelper,
    AggAwcDistributedHelper,
    AggChildHealthAggregationDistributedHelper,
    GrowthMonitoringFormsAggregationDistributedHelper,
    DailyFeedingFormsChildHealthAggregationDistributedHelper,
)
from custom.icds_reports.utils.aggregation_helpers.distributed.location_reassignment import (
    TempPrevUCRTables,
    TempPrevIntermediateTables,
    TempInfraTables
)
from custom.icds_reports.utils.aggregation_helpers.distributed.mbt import (
    AwcMbtDistributedHelper,
    CcsMbtDistributedHelper,
    ChildHealthMbtDistributedHelper,
)

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
    {'type': 'ls_usage','name':'static-ls_usage_forms'},
    {'type': 'ls_home_visits', 'name': 'static-ls_home_visit_forms_filled'},
    {'type': 'ls_awc_mgt', 'name': 'static-awc_mgt_forms'},
    {'type': 'cbe_form', 'name': 'static-cbe_form'},
    {'type': 'thr_form_v2', 'name': 'static-thr_forms_v2'}
]

SQL_FUNCTION_PATHS = [
    ('migrations', 'sql_templates', 'database_functions', 'update_months_table.sql'),
    ('migrations', 'sql_templates', 'database_functions', 'create_new_agg_table_for_month.sql'),
]


@serial_task('{date}', timeout=36 * 60 * 60, queue='icds_aggregation_queue')
def move_ucr_data_into_aggregation_tables(date=None, intervals=2):
    start_time = datetime.now(pytz.utc)
    date = date or start_time.date()
    monthly_dates = _get_monthly_dates(date, intervals)

    # probably this should be run one time, for now I leave this in aggregations script (not a big cost)
    # but remove issues when someone add new table to mapping, also we don't need to add new rows manually
    # on production servers
    _update_ucr_table_mapping()

    db_alias = get_icds_ucr_citus_db_alias()
    if db_alias:
        with connections[db_alias].cursor() as cursor:
            _create_aggregate_functions(cursor)

        update_aggregate_locations_tables()


        state_ids = list(SQLLocation.objects
                     .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
                     .values_list('location_id', flat=True))

        for monthly_date in monthly_dates:
            TempPrevUCRTables().make_all_tables(monthly_date)
            TempPrevIntermediateTables().make_all_tables(monthly_date)
            TempInfraTables().make_all_tables(monthly_date)
            calculation_date = monthly_date.strftime('%Y-%m-%d')
            res_daily = icds_aggregation_task.delay(date=calculation_date, func_name='_daily_attendance_table')
            res_daily.get(disable_sync_subtasks=False)

            drop_gm_indices(monthly_date)
            drop_df_indices(monthly_date)
            stage_1_tasks = [
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_gm_forms')
                for state_id in state_ids
            ]
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_df_forms')
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_cf_forms')
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_ccs_cf_forms')
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_child_health_thr_forms')
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_ccs_record_thr_forms')
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_child_health_pnc_forms'
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_ccs_record_pnc_forms'
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_delivery_forms'
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(
                    state_id=state_id, date=monthly_date, func_name='_aggregate_bp_forms'
                ) for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date, func_name='_aggregate_awc_infra_forms')
                for state_id in state_ids
            ])
            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=calculation_date, func_name='_agg_thr_table')
                for state_id in state_ids
            ])

            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date,
                                               func_name='_agg_adolescent_girls_registration_table')
                for state_id in state_ids
            ])

            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date,
                                               func_name='_agg_migration_table')
                for state_id in state_ids
            ])

            stage_1_tasks.extend([
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date,
                                               func_name='_agg_availing_services_table')
                for state_id in state_ids
            ])

            stage_1_tasks.append(icds_aggregation_task.si(date=calculation_date, func_name='_update_months_table'))

            # https://github.com/celery/celery/issues/4274
            stage_1_task_results = [stage_1_task.delay() for stage_1_task in stage_1_tasks]
            for stage_1_task_result in stage_1_task_results:
                stage_1_task_result.get(disable_sync_subtasks=False)

            create_df_indices(monthly_date)
            res_child = chain(
                icds_state_aggregation_task.si(
                    state_id=state_ids, date=calculation_date, func_name='_child_health_monthly_table'
                ),
                icds_aggregation_task.si(date=calculation_date, func_name='_agg_child_health_table')
            ).apply_async()
            res_ccs = chain(
                icds_aggregation_task.si(date=calculation_date, func_name='_ccs_record_monthly_table'),
                icds_aggregation_task.si(date=calculation_date, func_name='_agg_ccs_record_table'),
            ).apply_async()

            res_ccs.get(disable_sync_subtasks=False)
            res_child.get(disable_sync_subtasks=False)

            res_ls_tasks = list()
            res_ls_tasks.extend([icds_state_aggregation_task.si(state_id=state_id, date=calculation_date,
                                                                func_name='_agg_ls_awc_mgt_form')
                                 for state_id in state_ids
                                 ])
            res_ls_tasks.extend([icds_state_aggregation_task.si(state_id=state_id, date=calculation_date,
                                                                func_name='_agg_ls_vhnd_form')
                                 for state_id in state_ids
                                 ])
            res_ls_tasks.extend([icds_state_aggregation_task.si(state_id=state_id, date=calculation_date,
                                                                func_name='_agg_beneficiary_form')
                                 for state_id in state_ids
                                 ])

            res_ls_tasks.append(icds_aggregation_task.si(date=calculation_date, func_name='_agg_ls_table'))

            res_sdr = chain(icds_aggregation_task.si(date=calculation_date, func_name='update_service_delivery_report'),
                            ).apply_async()

            res_sdr.get(disable_sync_subtasks=False)

            res_inactive_aww = chain(icds_aggregation_task.si(date=calculation_date, func_name='_aggregate_inactive_aww_agg'),).apply_async()

            res_inactive_aww.get(disable_sync_subtasks=False)

            res_awc = chain(icds_aggregation_task.si(date=calculation_date, func_name='_agg_awc_table'),
                            *res_ls_tasks
                            ).apply_async()

            res_awc.get(disable_sync_subtasks=False)

            first_of_month_string = monthly_date.strftime('%Y-%m-01')
            for state_id in state_ids:
                create_mbt_for_month.delay(state_id, first_of_month_string)
        chain(
            icds_aggregation_task.si(date=date.strftime('%Y-%m-%d'), func_name='aggregate_awc_daily'),
            email_dashboad_team.si(aggregation_date=date.strftime('%Y-%m-%d'), aggregation_start_time=start_time)
        ).delay()


def _get_monthly_dates(start_date, total_intervals):
    """
    Gets a list of dates for the aggregation. Which all take the form of the last of the month.
    :param start_date: The date to start from
    :param total_intervals: The number of intervals (including start_date).
    :return: A list of dates containing the last day of the month before `start_date` and the specified
    number of intervals (including `start_date`).
    """
    monthly_dates = []

    first_day_of_month = start_date.replace(day=1)
    for interval in range(total_intervals - 1, 0, -1):
        # calculate the last day of the previous months to send to the aggregation script
        first_day_next_month = first_day_of_month - relativedelta(months=interval - 1)
        monthly_dates.append(first_day_next_month - relativedelta(days=1))

    monthly_dates.append(start_date)
    return monthly_dates


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


def update_aggregate_locations_tables():
    try:
        celery_task_logger.info("Starting icds reports update_location_tables")
        with transaction.atomic(using=router.db_for_write(AwcLocation)):
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
def icds_aggregation_task(self, date, func_name):
    func = {
        '_agg_ls_table': _agg_ls_table,
        '_update_months_table': _update_months_table,
        '_daily_attendance_table': _daily_attendance_table,
        '_agg_child_health_table': _agg_child_health_table,
        '_ccs_record_monthly_table': _ccs_record_monthly_table,
        '_agg_ccs_record_table': _agg_ccs_record_table,
        '_agg_awc_table': _agg_awc_table,
        'aggregate_awc_daily': aggregate_awc_daily,
        'update_service_delivery_report': update_service_delivery_report,
        '_aggregate_inactive_aww_agg': _aggregate_inactive_aww_agg
    }[func_name]

    db_alias = get_icds_ucr_citus_db_alias()
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
                'Citus', func.__name__, settings.SERVER_ENVIRONMENT, date
            )
        )
        self.retry(exc=exc)

    celery_task_logger.info("Ended icds reports {} {}".format(date, func.__name__))


@task(serializer='pickle', queue='icds_aggregation_queue', bind=True, default_retry_delay=15 * 60, acks_late=True)
def icds_state_aggregation_task(self, state_id, date, func_name):
    func = {
        '_aggregate_gm_forms': _aggregate_gm_forms,
        '_aggregate_cf_forms': _aggregate_cf_forms,
        '_aggregate_ccs_cf_forms': _aggregate_ccs_cf_forms,
        '_aggregate_child_health_thr_forms': _aggregate_child_health_thr_forms,
        '_aggregate_ccs_record_thr_forms': _aggregate_ccs_record_thr_forms,
        '_aggregate_child_health_pnc_forms': _aggregate_child_health_pnc_forms,
        '_aggregate_ccs_record_pnc_forms': _aggregate_ccs_record_pnc_forms,
        '_aggregate_delivery_forms': _aggregate_delivery_forms,
        '_aggregate_df_forms': _aggregate_df_forms,
        '_aggregate_bp_forms': _aggregate_bp_forms,
        '_aggregate_awc_infra_forms': _aggregate_awc_infra_forms,
        '_child_health_monthly_table': _child_health_monthly_table,
        '_agg_ls_awc_mgt_form': _agg_ls_awc_mgt_form,
        '_agg_ls_vhnd_form': _agg_ls_vhnd_form,
        '_agg_beneficiary_form': _agg_beneficiary_form,
        '_agg_thr_table': _agg_thr_table,
        '_agg_adolescent_girls_registration_table': _agg_adolescent_girls_registration_table,
        '_agg_migration_table': _agg_migration_table,
        '_agg_availing_services_table': _agg_availing_services_table
    }[func_name]

    db_alias = get_icds_ucr_citus_db_alias()
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
        _dashboard_team_soft_assert(
            False,
            "{} aggregation failed on {} for {} on {}. This task will be retried in 15 minutes".format(
                func.__name__, settings.SERVER_ENVIRONMENT, state_id, date
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
def _aggregate_inactive_aww(day):
    AggregateInactiveAWW.aggregate(day)


def _aggregate_inactive_aww_agg(day=None):
    last_sync = IcdsFile.objects.filter(data_type='inactive_awws').order_by('-file_added').first()

    # If last sync not exist then collect initial data
    if not last_sync:
        last_sync_date = datetime(2017, 3, 1).date()
    else:
        last_sync_date = last_sync.file_added

    AggregateInactiveAWW.aggregate(last_sync_date)


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

    agg_daily_dates = [{
        'date': force_to_date(day) - timedelta(days=2),
        'use_agg_awc': False},
        {'date': force_to_date(day) - timedelta(days=1),
        'use_agg_awc': False},
        {'date': force_to_date(day),
         'use_agg_awc': True}]

    for daily_date in agg_daily_dates:
        with transaction.atomic(using=router.db_for_write(AggAwcDaily)):
            AggAwcDaily.aggregate(date=daily_date['date'], use_agg_awc=daily_date['use_agg_awc'])


@track_time
def _update_months_table(day):
    db_alias = router.db_for_write(IcdsMonths)
    _run_custom_sql_script(["SELECT update_months_table(%s)"], day, db_alias=db_alias)


def get_cursor(model, write=True):
    db = router.db_for_write(model) if write else router.db_for_read(model)
    return connections[db].cursor()


def _child_health_monthly_table(state_ids, day):
    _child_health_monthly_data(state_ids, day)
    update_child_health_monthly_table.delay(day, state_ids)



def _child_health_monthly_data(state_ids, day):
    helper = ChildHealthMonthlyAggregationDistributedHelper(state_ids, force_to_date(day))

    celery_task_logger.info("Creating temporary table")
    with get_cursor(ChildHealthMonthly) as cursor:
        cursor.execute(helper.drop_temporary_table())
        cursor.execute(helper.create_temporary_table())
        for state in state_ids:
            cursor.execute(helper.drop_partition(state))
            cursor.execute(helper.create_partition(state))

    # https://github.com/celery/celery/issues/4274
    sub_aggregations = [
        _child_health_helper.delay(list(queries))
        for queries in helper.pre_aggregation_queries()
    ]
    for sub_aggregation in sub_aggregations:
        sub_aggregation.get(disable_sync_subtasks=False)


@task(serializer='pickle', queue='icds_aggregation_queue', default_retry_delay=15 * 60, acks_late=True)
def update_child_health_monthly_table(day, state_ids):
    celery_task_logger.info("Inserting into child_health_monthly_table")
    with transaction.atomic(using=router.db_for_write(ChildHealthMonthly)):
        ChildHealthMonthly.aggregate(state_ids, force_to_date(day))


@task(serializer='pickle', queue='icds_aggregation_queue', default_retry_delay=15 * 60, acks_late=True)
@track_time
def _child_health_helper(queries):
    with get_cursor(ChildHealthMonthly) as cursor:
        for query, params in queries:
            celery_task_logger.info("Running child_health_helper with %s", params)
            cursor.execute(query, params)
        celery_task_logger.info("Completed child_health_helper with %s", params)


@track_time
def _ccs_record_monthly_table(day):
    with transaction.atomic(using=router.db_for_write(CcsRecordMonthly)):
        CcsRecordMonthly.aggregate(force_to_date(day))


@track_time
def _daily_attendance_table(day):
    DailyAttendance.aggregate(force_to_date(day))


@track_time
def _agg_child_health_table(day):
    AggChildHealth.aggregate(force_to_date(day))


def agg_child_health_temp(day):
    helper = AggChildHealthAggregationDistributedHelper(force_to_date(day))
    with get_cursor(AggChildHealth) as cursor:
        helper.aggregate_temp(cursor)


def update_agg_child_health(day):
    helper = AggChildHealthAggregationDistributedHelper(force_to_date(day))
    with get_cursor(AggChildHealth) as cursor:
        helper.update_table(cursor)


@track_time
def _agg_ccs_record_table(day):
    db_alias = router.db_for_write(AggCcsRecord)
    with transaction.atomic(using=db_alias):
        _run_custom_sql_script([
            "SELECT create_new_aggregate_table_for_month('agg_ccs_record', %s)",
        ], day, db_alias=db_alias)
        AggCcsRecord.aggregate(force_to_date(day))


@track_time
def _agg_awc_table(day):
    db_alias = router.db_for_write(AggAwc)
    helper = AggAwcDistributedHelper(force_to_date(day))
    with get_cursor(AggAwc) as cursor:
        cursor.execute(helper.drop_temporary_table())
    with transaction.atomic(using=db_alias):
        _run_custom_sql_script([
            "SELECT create_new_aggregate_table_for_month('agg_awc', %s)"
        ], day, db_alias=db_alias)
        AggAwc.aggregate(force_to_date(day))


@track_time
def _agg_ls_vhnd_form(state_id, day):
    with transaction.atomic(using=router.db_for_write(AggLs)):
        AggregateLsVhndForm.aggregate(state_id, force_to_date(day))


@track_time
def _agg_beneficiary_form(state_id, day):
    with transaction.atomic(using=router.db_for_write(AggLs)):
        AggregateBeneficiaryForm.aggregate(state_id, force_to_date(day))


@track_time
def _agg_ls_awc_mgt_form(state_id, day):
    with transaction.atomic(using=router.db_for_write(AggLs)):
        AggregateLsAWCVisitForm.aggregate(state_id, force_to_date(day))


@track_time
def _agg_ls_table(day):
    with transaction.atomic(using=router.db_for_write(AggLs)):
        AggLs.aggregate(force_to_date(day))


@track_time
def _agg_thr_table(state_id, day):
    with transaction.atomic(using=router.db_for_write(AggregateTHRForm)):
        AggregateTHRForm.aggregate(state_id, force_to_date(day))

@track_time
def _agg_adolescent_girls_registration_table(state_id, day):
    db_alias = router.db_for_write(AggregateAdolescentGirlsRegistrationForms)
    with transaction.atomic(using=db_alias):
        AggregateAdolescentGirlsRegistrationForms.aggregate(state_id, force_to_date(day))


@track_time
def _agg_migration_table(state_id, day):
    db_alias = router.db_for_write(AggregateMigrationForms)
    with transaction.atomic(using=db_alias):
        AggregateMigrationForms.aggregate(state_id, force_to_date(day))


@track_time
def _agg_availing_services_table(state_id, day):
    db_alias = router.db_for_write(AggregateAvailingServiceForms)
    with transaction.atomic(using=db_alias):
        AggregateAvailingServiceForms.aggregate(state_id, force_to_date(day))


@task(serializer='pickle', queue='icds_aggregation_queue')
def email_dashboad_team(aggregation_date, aggregation_start_time):
    aggregation_start_time = aggregation_start_time.astimezone(INDIA_TIMEZONE)
    aggregation_finish_time = datetime.now(INDIA_TIMEZONE)

    # temporary soft assert to verify it's completing
    if not settings.UNIT_TESTING:
        citus = 'Citus '
        timings = "Aggregation Started At : {} IST, Completed At : {} IST".format(aggregation_start_time,
                                                                                  aggregation_finish_time)
        _dashboard_team_soft_assert(False, "{}Aggregation completed on {}".format(citus,
                                                                                  settings.SERVER_ENVIRONMENT),
                                    timings)
    celery_task_logger.info("Aggregation has completed")
    icds_data_validation.delay(aggregation_date)


@periodic_task_on_envs(
    settings.ICDS_ENVS,
    queue='background_queue',
    run_every=crontab(day_of_week='tuesday,thursday,saturday', minute=0, hour=16),
    acks_late=True
)
def recalculate_stagnant_child_health_cases(latest_datetime='1970-01-01'):
    stagnant_date = datetime.utcnow() - timedelta(days=26)
    last_processed_datetime = _recalculate_stagnant_cases(
        'static-icds-cas-static-child_cases_monthly_v2',
        force_to_datetime(latest_datetime)
    )

    if stagnant_date < last_processed_datetime:
        # We've processed past the point of "stagnant"
        return
    if latest_datetime == last_processed_datetime:
        notify_exception(None, message="BATCH_SIZE not large enough in stagnant case calculations")
        return
    recalculate_stagnant_child_health_cases.delay(last_processed_datetime)


@periodic_task_on_envs(
    settings.ICDS_ENVS,
    queue='background_queue',
    run_every=crontab(day_of_week='tuesday,thursday,saturday', minute=0, hour=16),
    acks_late=True
)
def recalculate_stagnant_ccs_record_cases(latest_datetime='1970-01-01'):
    stagnant_date = datetime.utcnow() - timedelta(days=26)
    last_processed_datetime = _recalculate_stagnant_cases(
        'static-icds-cas-static-ccs_record_cases_monthly_v2',
        force_to_datetime(latest_datetime)
    )
    if stagnant_date < last_processed_datetime:
        # We've processed past the point of "stagnant"
        return
    if latest_datetime == last_processed_datetime:
        notify_exception(None, message="BATCH_SIZE not large enough in stagnant case calculations")
        return
    recalculate_stagnant_ccs_record_cases.delay(last_processed_datetime)


def _recalculate_stagnant_cases(config_id, latest_datetime):
    config, is_static = get_datasource_config(config_id, DASHBOARD_DOMAIN)
    adapter = get_indicator_adapter(config, load_source='find_stagnant_cases')
    num_cases = 0
    last_processed_datetime = latest_datetime
    for case_id, inserted_at in _find_stagnant_cases(adapter, latest_datetime):
        AsyncIndicator.update_record(case_id, 'CommCareCase', DASHBOARD_DOMAIN, [config_id])
        num_cases += 1
        last_processed_datetime = max(last_processed_datetime, inserted_at)
    adapter.track_load(num_cases)
    celery_task_logger.info(
        f"Found {num_cases} stagnant cases in config {config_id}"
        "between {latest_datetime} and {last_processed_datetime}"
    )
    return last_processed_datetime


def _find_stagnant_cases(adapter, latest_datetime):
    BATCH_SIZE = 10000
    table = adapter.get_table()
    query_object = adapter.get_query_object()
    return (
        query_object.with_entities(table.c.doc_id, table.c.inserted_at).filter(
            table.c.inserted_at >= latest_datetime,
            table.c.inserted_at <= datetime.utcnow()  # This filter is used to force postgres to use the index
        ).distinct().order_by(table.c.inserted_at)[:BATCH_SIZE]
    )


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

        if file_format == 'xlsx':
            cache_key = create_child_report_excel_file(
                excel_data,
                data_type,
                config['month'].strftime("%B %Y"),
                aggregation_level,
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)

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
            show_test=include_test,
            beta=beta
        ).get_excel_data(
            location,
            system_usage_num_launched_awcs_formatting_at_awc_level=aggregation_level > 4 and beta,
            system_usage_num_of_days_awc_was_open_formatting=aggregation_level <= 4 and beta,
            system_usage_num_of_lss_formatting=aggregation_level <= 4 and beta,
        )
    elif indicator == AWC_INFRASTRUCTURE_EXPORT:
        data_type = 'AWC_Infrastructure'
        excel_data = AWCInfrastructureExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta,
        ).get_excel_data(location)
    elif indicator == GROWTH_MONITORING_LIST_EXPORT:
        # this report doesn't use this configuration
        config.pop('aggregation_level', None)
        data_type = 'Growth_Monitoring_list'
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
            beta=beta,
            report_type=config['thr_report_type']
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
                config['thr_report_type'],
                beta=beta
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)
    elif indicator == DASHBOARD_USAGE_EXPORT:
        excel_data = DashBoardUsage(
            couch_user=config['couch_user'],
            domain=config['domain']
        ).get_excel_data()
        export_info = excel_data[1][1]
        generated_timestamp = date_parser.parse(export_info[0][1])
        formatted_timestamp = generated_timestamp.strftime("%d-%m-%Y__%H-%M-%S")
        data_type = 'Dashboard Activity Report__{}'.format(formatted_timestamp)
        if file_format == 'xlsx':
            cache_key = get_dashboard_usage_excel_file(
                excel_data,
                data_type
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)
    elif indicator == SERVICE_DELIVERY_REPORT:
        excel_data = ServiceDeliveryReport(
            config=config,
            location=location,
            beta=beta
        ).get_excel_data()
        export_info = excel_data[1][1]
        generated_timestamp = date_parser.parse(export_info[0][1])
        formatted_timestamp = generated_timestamp.strftime("%d-%m-%Y__%H-%M-%S")
        data_type = 'Service Delivery Report__{}'.format(formatted_timestamp)

        if file_format == 'xlsx':
            cache_key = create_service_delivery_report(
                excel_data,
                data_type,
                config,
                beta
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)

        formatted_timestamp = datetime.now().strftime("%d-%m-%Y__%H-%M-%S")
        data_type = 'Service Delivery Report__{}'.format(formatted_timestamp)
    elif indicator == CHILD_GROWTH_TRACKER_REPORT:
        config.pop('aggregation_level', None)
        data_type = 'Child_Growth_Tracker_list'
        excel_data = GrowthTrackerExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta
        ).get_excel_data(location)
        export_info = excel_data[1][1]
        generated_timestamp = date_parser.parse(export_info[0][1])
        formatted_timestamp = generated_timestamp.strftime("%d-%m-%Y__%H-%M-%S")
        data_type = 'Child Growth Tracker Report__{}'.format(formatted_timestamp)

        if file_format == 'xlsx':
            cache_key = create_child_growth_tracker_report(
                excel_data,
                data_type,
                config,
                aggregation_level
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)

    elif indicator == AWW_ACTIVITY_REPORT:
        data_type = 'AWW_Activity_Report'
        excel_data = AwwActivityExport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta
        ).get_excel_data(location)
        export_info = excel_data[1][1]
        generated_timestamp = date_parser.parse(export_info[0][1])
        formatted_timestamp = generated_timestamp.strftime("%d-%m-%Y__%H-%M-%S")
        data_type = 'AWW_Activity_Report__{}'.format(formatted_timestamp)

        if file_format == 'xlsx':
            cache_key = create_aww_activity_report(
                excel_data,
                data_type,
                config,
                aggregation_level
            )
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)

    elif indicator == POSHAN_PROGRESS_REPORT:
        data_type = 'Poshan_Progress_Report'
        excel_data = PoshanProgressReport(
            config=config,
            loc_level=aggregation_level,
            show_test=include_test,
            beta=beta
        ).get_excel_data(location)
        export_info = excel_data[1][1]
        generated_timestamp = date_parser.parse(export_info[0][1])
        formatted_timestamp = generated_timestamp.strftime("%d-%m-%Y__%H-%M-%S")
        report_layout = config['report_layout']
        data_type = 'Poshan Progress Report {report_layout}__{formatted_timestamp}'.format(
            report_layout=report_layout,
            formatted_timestamp=formatted_timestamp)

        if file_format == 'xlsx':
            cache_key = create_poshan_progress_report(excel_data, data_type, config, aggregation_level)
        else:
            cache_key = create_excel_file(excel_data, data_type, file_format)

    if indicator not in (AWW_INCENTIVE_REPORT, LS_REPORT_EXPORT, THR_REPORT_EXPORT, CHILDREN_EXPORT,
                         DASHBOARD_USAGE_EXPORT, SERVICE_DELIVERY_REPORT, CHILD_GROWTH_TRACKER_REPORT,
                         AWW_ACTIVITY_REPORT, POSHAN_PROGRESS_REPORT):
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
    if all(len(v) == 0 for _, v in bad_data.items()):
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
@periodic_task_on_envs(
    settings.ICDS_ENVS,
    run_every=crontab(minute=30, hour=18),
    acks_late=True,
    queue='icds_aggregation_queue'
)
def collect_inactive_awws():
    from custom.icds.messaging.indicators import is_aggregate_inactive_aww_data_fresh
    celery_task_logger.info("Started updating the Inactive AWW")
    filename = "inactive_awws_%s.csv" % date.today().strftime('%Y-%m-%d')
    last_sync = IcdsFile.objects.filter(data_type='inactive_awws').order_by('-file_added').first()

    # If last sync not exist then collect initial data
    if not last_sync:
        last_sync_date = datetime(2017, 3, 1).date()
    else:
        last_sync_date = last_sync.file_added

    _aggregate_inactive_aww(last_sync_date)

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
    is_aggregate_inactive_aww_data_fresh.clear()
    celery_task_logger.info("Ended updating the Inactive AWW")


@periodic_task_on_envs(settings.ICDS_ENVS, run_every=crontab(day_of_week='monday', hour=0, minute=0),
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

@periodic_task_on_envs(settings.ICDS_ENVS, run_every=crontab(day_of_week=5, hour=14, minute=0),
                       acks_late=True, queue='icds_aggregation_queue')
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


@task(queue='icds_dashboard_reports_queue', serializer='pickle')
def build_missing_disha_dump(month, state_name):
    # the params should already be validated and cleaned
    assert month < date.today()
    DishaDump(state_name, month).build_export_json(query_master=True)


@periodic_task_on_envs(settings.ICDS_ENVS, run_every=crontab(hour=17, minute=0, day_of_month='12'),
                       acks_late=True, queue='icds_aggregation_queue')
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

    aggregate_validation_helper.delay(agg_date)

    for file_format in ['xlsx', 'csv']:
        for location in locations:
            if location.location_type.name == 'state':
                build_incentive_files.delay(location, agg_date, file_format, 1, location)
            elif location.location_type.name == 'district':
                build_incentive_files.delay(location, agg_date, file_format, 2, location.parent, location)
            else:
                build_incentive_files.delay(location, agg_date, file_format, 3, location.parent.parent, location.parent)


@task(queue='icds_dashboard_reports_queue', serializer='pickle')
def aggregate_validation_helper(agg_date):
    """
    Validates the performance reports vs aggregate reports and send mails with mismatches
    """
    awc_performance_rows_list = list(AWWIncentiveReport.objects.filter(month=agg_date)
                                     .values('awc_id', 'is_launched', 'valid_visits', 'visit_denominator',
                                             'wer_weighed', 'wer_eligible', 'incentive_eligible')
                                     .order_by('awc_id'))
    awc_aggregate_rows_list = list(AggAwc.objects.filter(aggregation_level=5, month=agg_date)
                                   .values('awc_id', 'is_launched', 'valid_visits', 'expected_visits')
                                   .order_by('awc_id'))
    is_launched_check_bad_data = []
    home_conduct_check_bad_data = []
    eligibility_check_bad_data = []
    missed_ids_from_performance = []
    missed_ids_from_aggregate = []
    performance_index = 0
    aggregate_index = 0
    while performance_index < len(awc_performance_rows_list) and aggregate_index < len(awc_aggregate_rows_list):
        awc_from_performance = awc_performance_rows_list[performance_index]
        awc_from_aggregate = awc_aggregate_rows_list[aggregate_index]
        awc_id_from_performance = awc_from_performance['awc_id']
        awc_id_from_aggregate = awc_from_aggregate['awc_id']
        # skipping unmatched rows
        while awc_id_from_performance != awc_id_from_aggregate:
            if awc_id_from_performance > awc_id_from_aggregate:
                missed_ids_from_performance.append(awc_id_from_performance)
                aggregate_index += 1
            else:
                missed_ids_from_aggregate.append(awc_id_from_aggregate)
                performance_index += 1
            awc_from_performance = awc_performance_rows_list[performance_index]
            awc_from_aggregate = awc_aggregate_rows_list[aggregate_index]

        # check for launched AWCs
        row_data = get_awc_is_launched_mismatch_row(awc_from_performance, awc_from_aggregate)
        if row_data is not None:
            is_launched_check_bad_data.append(row_data)

        # check for home conduct percentage
        row_data = get_awc_home_conduct_mismatch_row(awc_from_performance, awc_from_aggregate)
        if row_data is not None:
            home_conduct_check_bad_data.append(row_data)

        # check for eligibility
        row_data = get_awc_eligibility_mismatch_row(awc_from_performance)
        if row_data is not None:
            eligibility_check_bad_data.append(row_data)

        # incrementing the indexes
        performance_index += 1
        aggregate_index += 1

    mismatched_performance_awc_ids_length = len(missed_ids_from_performance)
    mismatched_aggregate_awc_ids_length = len(missed_ids_from_aggregate)

    awc_ids_mismatch_count = mismatched_performance_awc_ids_length
    if mismatched_performance_awc_ids_length < mismatched_aggregate_awc_ids_length:
        awc_ids_mismatch_count = mismatched_aggregate_awc_ids_length

    # merging two mismatched awc_ids into a single list
    awc_ids_mismatched_list = []
    for i in range(awc_ids_mismatch_count):
        try:
            awc_id_mismatched_row = [missed_ids_from_performance[i], missed_ids_from_aggregate[i]]
        except IndexError:
            if i >= mismatched_performance_awc_ids_length:
                missed_ids_from_performance.append('')
            if i >= mismatched_aggregate_awc_ids_length:
                missed_ids_from_aggregate.append('')
            awc_id_mismatched_row = [missed_ids_from_performance[i], missed_ids_from_aggregate[i]]
        awc_ids_mismatched_list.append(awc_id_mismatched_row)

    file_attachments = []
    if len(is_launched_check_bad_data) > 0:
        csv_columns = ['awc_id_from_performance', 'awc_id_from_aggregate', 'AwwIncentiveReport', 'AggAwc']
        file_attachments.append({"csv_columns": csv_columns, "data": is_launched_check_bad_data,
                                 "filename": datetime.now().strftime('incentive_report_awc_is_launched_mismatch'
                                                                     '_%s.csv' % SERVER_DATETIME_FORMAT)})

    if len(home_conduct_check_bad_data) > 0:
        csv_columns = ['awc_id_from_performance', 'awc_id_from_aggregate', 'AwwIncentiveReport', 'AggAwc']
        file_attachments.append({"csv_columns": csv_columns, "data": home_conduct_check_bad_data,
                                 "filename": datetime.now().strftime('incentive_report_awc_home_conduct mismatch'
                                                                     '_%s.csv' % SERVER_DATETIME_FORMAT)})

    if len(eligibility_check_bad_data) > 0:
        csv_columns = ['awc_id_from_performance', 'Expected eligibility', 'Eligibility from performance record']
        file_attachments.append({"csv_columns": csv_columns, "data": eligibility_check_bad_data,
                                 "filename": datetime.now().strftime('incentive_report_awc_eligibility_mismatch'
                                                                     '_%s.csv' % SERVER_DATETIME_FORMAT)})

    if awc_ids_mismatch_count > 0:
        csv_columns = ['awc_ids_from_performance', 'awc_ids_from_aggregate']
        file_attachments.append({"csv_columns": csv_columns, "data": awc_ids_mismatched_list,
                                 "filename": datetime.now().strftime('incentive_report_awc_ids_mismatch'
                                                                     '_%s.csv' % SERVER_DATETIME_FORMAT)})

    if len(file_attachments) > 0:
        # sending email with mismatches
        _send_incentive_report_validation_email(file_attachments)


def get_awc_is_launched_mismatch_row(performance_row, awcagg_row):
    """
    :param performance_row: AWCIncentiveReport object with 'awc_id', 'is_launched', 'valid_visits',
     'visit_denominator', 'wer_weighed', 'wer_eligible', 'incentive_eligible'.
    :param awcagg_row: AggAwc object with 'awc_id', 'is_launched', 'valid_visits', 'expected_visits'
    :return: None if no mismatch or returns a row with awc_id from performance report, awc_id from
     aggregate report, is_launched from performance report and is_launched from aggregate report
    """
    is_launched_from_awc = False
    if awcagg_row['is_launched'].lower() == 'yes':
        is_launched_from_awc = True
    # checking if is_launched from incentive report is same as that of aggregate
    if performance_row['is_launched'] != is_launched_from_awc:
        row_data = [performance_row['awc_id'], awcagg_row['awc_id'], performance_row['is_launched'],
                    is_launched_from_awc]
        return row_data
    return None


def get_awc_home_conduct_mismatch_row(performance_row, awcagg_row):
    """
    :param performance_row: AWCIncentiveReport object with 'awc_id', 'is_launched', 'valid_visits',
     'visit_denominator', 'wer_weighed', 'wer_eligible', 'incentive_eligible'.
    :param awcagg_row: AggAwc object with 'awc_id', 'is_launched', 'valid_visits', 'expected_visits'
    :return: None if no mismatch or returns a row with awc_id from performance report, awc_id from
     aggregate report, home_conduct percentage from performance report and home_conduct percentage
     from aggregate report
    """
    # checking if valid_visits or valid_denominator is zero or None as they are treated as valid cases
    if performance_row['valid_visits'] is None or performance_row['visit_denominator'] in [0, None]:
        home_conduct_from_report = 'None'
    else:
        home_conduct_from_report = performance_row['valid_visits'] / performance_row['visit_denominator']
    if awcagg_row['valid_visits'] is None or awcagg_row['expected_visits'] in [0, None]:
        home_conduct_from_awc = 'None'
    else:
        home_conduct_from_awc = awcagg_row['valid_visits'] / awcagg_row['expected_visits']
    # checking if home conduct (valid_visits/valid_denominator) from incentive report is same as that of aggregate
    if home_conduct_from_report != home_conduct_from_awc:
        row_data = [performance_row['awc_id'], awcagg_row['awc_id'], home_conduct_from_report,
                    home_conduct_from_awc]
        return row_data
    return None


def get_awc_eligibility_mismatch_row(performance_row):
    """
    :param performance_row: AWCIncentiveReport object with 'awc_id', 'is_launched', 'valid_visits',
     'visit_denominator', 'wer_weighed', 'wer_eligible', 'incentive_eligible'.
    :return: None if no mismatch or return a row with expected eligibility and actual eligibility
    """
    # checking if valid_visits or valid_denominator is zero or None as they are treated as valid cases
    if performance_row['valid_visits'] is None or performance_row['visit_denominator'] in [0, None]:
        is_eligible = True
    else:
        # checking if valid_visits/valid_denominator > 0.6(60%)
        home_conduct_from_report = performance_row['valid_visits'] / performance_row['visit_denominator']
        if home_conduct_from_report > 0.6:
            is_eligible = True
        else:
            is_eligible = False
    if is_eligible:
        # checking if wer_weighed or wer_eligible is zero or None as they are treated as valid cases
        if performance_row['wer_weighed'] is None or performance_row['wer_eligible'] in [0, None]:
            is_eligible = True
        else:
            # checking if wer_weighed/wer_eligible > 0.6(60%)
            weigh_eligibility = performance_row['wer_weighed'] / performance_row['wer_eligible']
            if weigh_eligibility > 0.6:
                is_eligible = True
            else:
                is_eligible = False
    if not performance_row['incentive_eligible']:
        if is_eligible and performance_row['is_launched']:
            return [performance_row['awc_id'], is_eligible and performance_row['is_launched'],
                    performance_row['incentive_eligible']]
    else:
        if not (is_eligible and performance_row['is_launched']):
            return [performance_row['awc_id'], is_eligible and performance_row['is_launched'],
                    performance_row['incentive_eligible']]
    return None


def _send_incentive_report_validation_email(mail_data_list):
    attachments_list = []
    for mail_item in mail_data_list:
        csv_file = io.StringIO()
        writer = csv.writer(csv_file)
        writer.writerow(mail_item['csv_columns'])
        for data in mail_item['data']:
            writer.writerow(data)
        attachments_list.append({'file_obj': csv_file, 'title': mail_item['filename'],
                                 'mimetype': 'text/csv'})
    email_content = """
    Please see the attachments for mismatch in awc performance report vs awc aggregate report
    """
    send_HTML_email(
        '[{}] - ICDS Dashboard AWC Incentive Report Mismatch'.format(settings.SERVER_ENVIRONMENT),
        DASHBOARD_TEAM_EMAILS, email_content, file_attachments=attachments_list
    )


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


def create_all_mbt(month, state_ids):
    first_of_month = month.strftime('%Y-%m-01')
    prev_month = month.replace(day=1) - relativedelta(months=1)
    prev_month_string = prev_month.strftime('%Y-%m-01')
    for state_id in state_ids:
        create_mbt_for_month.delay(state_id, prev_month_string)
        create_mbt_for_month.delay(state_id, first_of_month)


@task(queue='icds_dashboard_reports_queue')
def create_mbt_for_month(state_id, month):
    helpers = (CcsMbtDistributedHelper, ChildHealthMbtDistributedHelper, AwcMbtDistributedHelper)
    for helper_class in helpers:
        helper = helper_class(state_id, month)
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


def _dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def setup_aggregation(agg_date):
    _update_ucr_table_mapping()

    db_alias = get_icds_ucr_citus_db_alias()
    if db_alias:
        with connections[db_alias].cursor() as cursor:
            _create_aggregate_functions(cursor)
            TempPrevUCRTables().make_all_tables(force_to_date(agg_date))


def _child_health_monthly_aggregation(day, state_ids):
    helper = ChildHealthMonthlyAggregationDistributedHelper(state_ids, force_to_date(day))

    with get_cursor(ChildHealthMonthly) as cursor:
        celery_task_logger.info('dropping old temp table')
        cursor.execute(helper.drop_temporary_table())
        celery_task_logger.info('creating partition table')
        cursor.execute(helper.create_temporary_table())
        for state in state_ids:
            celery_task_logger.info(f'create state partition for {state}')
            cursor.execute(helper.drop_partition(state))
            cursor.execute(helper.create_partition(state))

    greenlets = []
    pool = Pool(20)
    for queries in helper.pre_aggregation_queries():
        greenlets.append(pool.spawn(_child_health_helper, queries))
    while not pool.join(timeout=120, raise_error=True):
        celery_task_logger.info('failed to join pool - greenlets remaining: {}'.format(len(pool)))
    for g in greenlets:
        g.get()


@task
def email_location_changes(domain, old_location_blob_id, new_location_blob_id):
    old_params = {
        'file_format': Format.UNZIPPED_CSV,
        'data_type': 'old_location_definitions',
        'uuid': old_location_blob_id,
    }
    new_params = {
        'file_format': Format.UNZIPPED_CSV,
        'data_type': 'new_location_definitions',
        'uuid': new_location_blob_id,
    }
    email_content = """
    Location data has changed. This can mean one or more of the following:

    * Locations were added
    * A location name was modified
    * The location hierarchy was modified
    * A user's name was modified

    To determine the exact change, please find the links to CSV changes below.
    Each file will only contain information on those AWCs which were added or changed:

    Old location definitions: {old_file_url}
    New location definitions: {new_file_url}

    NOTE this file contains identifiable data such as name and phone number.
    IT MAY ONLY BE SHARED CONFIDENTIALLY THROUGH SECURE MEANS.
    """.format(
        old_file_url=reverse('icds_download_excel', params=old_params, absolute=True, kwargs={'domain': domain}),
        new_file_url=reverse('icds_download_excel', params=new_params, absolute=True, kwargs={'domain': domain}),
    )

    send_HTML_email(
        '[{}] - ICDS Dashboard Location Table Changed'.format(settings.SERVER_ENVIRONMENT),
        DASHBOARD_TEAM_EMAILS, email_content,
    )


# run before aggregation (which is run at at 18:00 UTC)
@periodic_task_on_envs(settings.ICDS_ENVS, run_every=crontab(hour=16, minute=30))
def create_reconciliation_records():
    # Setup yesterday's data to reduce noise in case we're behind by a lot in pillows
    UcrReconciliationStatus.setup_days_records(date.today() - timedelta(days=1))
    for status in UcrReconciliationStatus.objects.filter(verified_date__isnull=True):
        reconcile_data_not_in_ucr.delay(status.pk)


@task(queue='dashboard_comparison_queue')
def reconcile_data_not_in_ucr(reconciliation_status_pk):
    status_record = UcrReconciliationStatus.objects.get(pk=reconciliation_status_pk)
    number_documents_missing = 0

    data_not_in_ucr = list(get_data_not_in_ucr(status_record))
    doc_ids_not_in_ucr = {data[0] for data in data_not_in_ucr}
    known_bad_doc_ids = set(
        InvalidUCRData.objects.filter(doc_id__in=doc_ids_not_in_ucr).values_list('doc_id', flat=True))

    if status_record.is_form_ucr:
        doc_ids_not_in_es = get_form_ids_missing_from_elasticsearch(doc_ids_not_in_ucr)
    else:
        doc_ids_not_in_es = get_case_ids_missing_from_elasticsearch(doc_ids_not_in_ucr)

    # republish_kafka_changes
    # running the data accessor again to avoid storing all doc ids in memory
    # since run time is relatively short and does not scale with number of errors
    # but the number of doc ids will increase with the number of errors
    for doc_id, doc_subtype, sql_modified_on in data_not_in_ucr:
        if doc_id in known_bad_doc_ids:
            # These docs are invalid
            continue
        number_documents_missing += 1
        not_found_in_es = doc_id in doc_ids_not_in_es
        celery_task_logger.info(f'doc_id {doc_id} from {sql_modified_on} not found in UCR data sources. '
            f'Not found in ES: {not_found_in_es}')
        send_change_for_ucr_reprocessing(doc_id, doc_subtype, status_record.is_form_ucr)

    metrics_counter(
        "commcare.icds.ucr_reconciliation.published_change_count",
        number_documents_missing,
        tags={'config_id': status_record.table_id, 'doc_type': status_record.doc_type},
        documentation="Number of docs that were not found in UCR that were republished"
    )
    metrics_counter(
        "commcare.icds.ucr_reconciliation.partially_processed_count",
        len(set(doc_ids_not_in_ucr) - set(doc_ids_not_in_es)),
        tags={'config_id': status_record.table_id, 'doc_type': status_record.doc_type},
        documentation="Number of docs that exists in Elasticsearch but are not found in UCR"
    )
    status_record.last_processed_date = datetime.utcnow()
    status_record.documents_missing = number_documents_missing
    if number_documents_missing == 0:
        status_record.verified_date = datetime.utcnow()
    status_record.save()

    return number_documents_missing


def send_change_for_ucr_reprocessing(doc_id, doc_subtype, is_form):
    producer.send_change(
        topics.FORM_SQL if is_form else topics.CASE_SQL,
        ChangeMeta(
            document_id=doc_id,
            data_source_type=data_sources.SOURCE_SQL,
            data_source_name=data_sources.FORM_SQL if is_form else data_sources.CASE_SQL,
            document_type='XFormInstance' if is_form else 'CommCareCase',
            document_subtype=doc_subtype,
            domain=DASHBOARD_DOMAIN,
            is_deletion=False,
        )
    )


def get_data_not_in_ucr(status_record):
    domain = DASHBOARD_DOMAIN
    if status_record.is_form_ucr:
        matching_records_for_db = _get_primary_data_for_forms(
            status_record.db_alias, domain, status_record.day, status_record.doc_type_filter
        )
    else:
        matching_records_for_db = _get_primary_data_for_cases(
            status_record.db_alias, domain, status_record.day, status_record.doc_type_filter
        )
    chunk_size = 1000
    for chunk in chunked(matching_records_for_db, chunk_size):
        doc_ids = [val[0] for val in chunk]
        doc_id_and_inserted_in_ucr = _get_docs_in_ucr(domain, status_record.table_id, doc_ids)
        for doc_id, doc_subtype, sql_modified_on in chunk:
            if doc_id in doc_id_and_inserted_in_ucr:
                # This is to handle the cases which are outdated. This condition also handles the time drift of 1 sec
                # between main db and ucr db. i.e  doc will even be included when inserted_at-sql_modified_on < 2 sec
                if sql_modified_on - doc_id_and_inserted_in_ucr[doc_id] > timedelta(seconds=-2):
                    yield (doc_id, doc_subtype, sql_modified_on.isoformat())
            else:
                yield (doc_id, doc_subtype, sql_modified_on.isoformat())


def _get_docs_in_ucr(domain, table_id, doc_ids):
    table_name = get_table_name(domain, table_id)
    with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
        query = f'''
            SELECT doc_id, inserted_at
            FROM "{table_name}"
            WHERE doc_id = ANY(%(doc_ids)s);
        '''
        cursor.execute(query, {'doc_ids': doc_ids})
        return {row[0]: row[1] for row in cursor.fetchall()}


def _get_primary_data_for_forms(db, domain, day, xmlns):
    start_date, end_date = day, day + timedelta(days=1)
    matching_xforms = XFormInstanceSQL.objects.using(db).filter(
        domain=domain,
        received_on__gte=start_date,
        received_on__lte=end_date,
        state=XFormInstanceSQL.NORMAL,
        xmlns=xmlns,
    )
    return matching_xforms.values_list('form_id', 'xmlns', 'received_on')


def _get_primary_data_for_cases(db, domain, day, case_type):
    start_date, end_date = day, day + timedelta(days=1)
    matching_cases = CommCareCaseSQL.objects.using(db).filter(
        domain=domain,
        server_modified_on__gte=start_date,
        server_modified_on__lte=end_date,
        type=case_type
    )
    return matching_cases.values_list('case_id', 'type', 'server_modified_on')


@periodic_task_on_envs(
    settings.ICDS_ENVS,
    run_every=crontab(minute=30, hour=0),  # To run on 6AM IST
    acks_late=True,
    queue='icds_aggregation_queue'
)
def update_dashboard_activity_report(target_date=None):
    if target_date is None:
        target_date = date.today()
    db_alias = router.db_for_write(DashboardUserActivityReport)
    with transaction.atomic(using=db_alias):
        DashboardUserActivityReport().aggregate(target_date)


def drop_gm_indices(agg_date):
    helper = GrowthMonitoringFormsAggregationDistributedHelper(None, agg_date)
    with get_cursor(AggregateGrowthMonitoringForms) as cursor:
        for query, params in helper.delete_queries():
            cursor.execute(query, params)
    helper.create_temporary_prev_table('static-child_health_cases')


def create_df_indices(agg_date):
    helper = DailyFeedingFormsChildHealthAggregationDistributedHelper(None, agg_date)
    with get_cursor(AggregateChildHealthDailyFeedingForms) as cursor:
        for query in helper.create_index_queries():
            cursor.execute(query)


def drop_df_indices(agg_date):
    helper = DailyFeedingFormsChildHealthAggregationDistributedHelper(None, agg_date)
    with get_cursor(AggregateChildHealthDailyFeedingForms) as cursor:
        for query, params in helper.delete_queries():
            cursor.execute(query, params)
        for query in helper.drop_index_queries():
            cursor.execute(query)


def cf_pre_queries(agg_date):
    helper = AggregateComplementaryFeedingForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-child_health_cases')


def ccs_cf_pre_queries(agg_date):
    helper = AggregateCcsRecordComplementaryFeedingForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-ccs_record_cases')


def migration_pre_queries(agg_date):
    helper = AggregateMigrationForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-person_cases_v3', 'person_case_id')


def availing_pre_queries(agg_date):
    helper = AggregateAvailingServiceForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-person_cases_v3', 'person_case_id')


def ch_pnc_pre_queries(agg_date):
    helper = AggregateChildHealthPostnatalCareForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-child_health_cases')


def ccs_pnc_pre_queries(agg_date):
    helper = AggregateCcsRecordPostnatalCareForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-ccs_record_cases')


def bp_pre_queries(agg_date):
    helper = AggregateBirthPreparednesForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-ccs_record_cases')


def ag_pre_queries(agg_date):
    helper = AggregateAdolescentGirlsRegistrationForms._agg_helper_cls(None, agg_date)
    helper.create_temporary_prev_table('static-person_cases_v3', 'person_case_id')


def awc_infra_pre_queries(agg_date):
    TempInfraTables().make_all_tables(agg_date)


def update_governance_dashboard(target_date):
    current_month = target_date.replace(day=1)
    _agg_governance_dashboard.delay(current_month)


@task(queue='icds_aggregation_queue', serializer='pickle')
def _agg_governance_dashboard(current_month):
    previous_month = current_month - relativedelta(months=1)
    for month in [previous_month, current_month]:
        db_alias = router.db_for_write(AggGovernanceDashboard)
        with transaction.atomic(using=db_alias):
            AggGovernanceDashboard().aggregate(month)


def update_service_delivery_report(target_date):
    current_month = force_to_date(target_date).replace(day=1)
    AggServiceDeliveryReport.aggregate(current_month)


def update_bihar_api_table(target_date):
    current_month = force_to_date(target_date).replace(day=1)
    _agg_bihar_api_demographics.delay(current_month)


@task(queue='icds_aggregation_queue', serializer='pickle')
def _agg_bihar_api_demographics(target_date):
    BiharAPIDemographics.aggregate(target_date)


def update_child_vaccine_table(target_date):
    current_month = force_to_date(target_date).replace(day=1)
    ChildVaccines.aggregate(current_month)
