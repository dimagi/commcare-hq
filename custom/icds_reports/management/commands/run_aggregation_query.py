from django.core.management.base import BaseCommand

import attr
import logging
import sys

from gevent.pool import Pool

from custom.icds_reports.models.util import AggregationRecord
from custom.icds_reports.tasks import (
    _agg_adolescent_girls_registration_table,
    _agg_availing_services_table,
    _agg_awc_table,
    _agg_beneficiary_form,
    _agg_ccs_record_table,
    _agg_ls_awc_mgt_form,
    _agg_ls_table,
    _agg_ls_vhnd_form,
    _agg_migration_table,
    _agg_thr_table,
    _aggregate_awc_infra_forms,
    _aggregate_bp_forms,
    _aggregate_ccs_cf_forms,
    _aggregate_ccs_record_pnc_forms,
    _aggregate_ccs_record_thr_forms,
    _aggregate_cf_forms,
    _aggregate_child_health_pnc_forms,
    _aggregate_child_health_thr_forms,
    _aggregate_delivery_forms,
    _aggregate_df_forms,
    _aggregate_gm_forms,
    _aggregate_inactive_aww_agg,
    _ccs_record_monthly_table,
    _child_health_monthly_aggregation,
    _daily_attendance_table,
    _update_months_table,
    ag_pre_queries,
    agg_child_health_temp,
    aggregate_awc_daily,
    awc_infra_pre_queries,
    availing_pre_queries,
    bp_pre_queries,
    ccs_cf_pre_queries,
    ccs_pnc_pre_queries,
    cf_pre_queries,
    ch_pnc_pre_queries,
    create_all_mbt,
    create_df_indices,
    drop_df_indices,
    drop_gm_indices,
    migration_pre_queries,
    setup_aggregation,
    update_agg_child_health,
    update_child_health_monthly_table,
    update_governance_dashboard,
    update_service_delivery_report,
    update_bihar_api_table,
    update_child_vaccine_table,
)


logger = logging.getLogger(__name__)

STATE_TASKS = {
    'aggregate_gm_forms': (drop_gm_indices, _aggregate_gm_forms, None),
    'aggregate_cf_forms': (cf_pre_queries, _aggregate_cf_forms, None),
    'aggregate_ccs_cf_forms': (ccs_cf_pre_queries, _aggregate_ccs_cf_forms, None),
    'aggregate_thr_forms': (None, _agg_thr_table, None),
    'aggregate_child_health_thr_forms': (None, _aggregate_child_health_thr_forms, None),
    'aggregate_ccs_record_thr_forms': (None, _aggregate_ccs_record_thr_forms, None),
    'aggregate_child_health_pnc_forms': (ch_pnc_pre_queries, _aggregate_child_health_pnc_forms, None),
    'aggregate_ccs_record_pnc_forms': (ccs_pnc_pre_queries, _aggregate_ccs_record_pnc_forms, None),
    'aggregate_delivery_forms': (None, _aggregate_delivery_forms, None),
    'aggregate_bp_forms': (bp_pre_queries, _aggregate_bp_forms, None),
    'aggregate_awc_infra_forms': (awc_infra_pre_queries, _aggregate_awc_infra_forms, None),
    'agg_ls_awc_mgt_form': (None, _agg_ls_awc_mgt_form, None),
    'agg_ls_vhnd_form': (None, _agg_ls_vhnd_form, None),
    'agg_beneficiary_form': (None, _agg_beneficiary_form, None),
    'aggregate_df_forms': (drop_df_indices, _aggregate_df_forms, create_df_indices),
    'aggregate_ag_forms': (ag_pre_queries, _agg_adolescent_girls_registration_table, None),
    'aggregate_migration_forms': (migration_pre_queries, _agg_migration_table, None),
    'aggregate_availing_services_forms': (availing_pre_queries, _agg_availing_services_table, None)
}

ALL_STATES_TASKS = {
    'child_health_monthly': (None, _child_health_monthly_aggregation, None),
    'create_mbt_for_month': (None, create_all_mbt, None),
    'update_child_health_monthly_table': (None, update_child_health_monthly_table, None),
}

NORMAL_TASKS = {
    'setup_aggregation': (None, setup_aggregation, None),
    'agg_ls_table': (None, _agg_ls_table, None),
    'update_months_table': (None, _update_months_table, None),
    'daily_attendance': (None, _daily_attendance_table, None),
    'agg_child_health_temp': (None, agg_child_health_temp, None),
    'ccs_record_monthly': (None, _ccs_record_monthly_table, None),
    'agg_ccs_record': (None, _agg_ccs_record_table, None),
    'agg_awc_table': (None, _agg_awc_table, None),
    'aggregate_awc_daily': (None, aggregate_awc_daily, None),
    'update_agg_child_health': (None, update_agg_child_health, None),
    'update_governance_dashboard': (None, update_governance_dashboard, None),
    'update_service_delivery_report': (None, update_service_delivery_report, None),
    'update_bihar_api_table': (None, update_bihar_api_table, None),
    'update_child_vaccine_table': (None, update_child_vaccine_table, None),
    'aggregate_inactive_aww_agg': (None, _aggregate_inactive_aww_agg, None)
}


SINGLE_STATE = 'single'
ALL_STATES = 'all'
NO_STATES = 'none'


@attr.s
class AggregationQuery(object):
    by_state = attr.ib()
    funcs = attr.ib()


function_map = {}


def setup_tasks():
    for name, funcs in STATE_TASKS.items():
        function_map[name] = AggregationQuery(SINGLE_STATE, funcs)
    for name, funcs in NORMAL_TASKS.items():
        function_map[name] = AggregationQuery(NO_STATES, funcs)
    for name, funcs in ALL_STATES_TASKS.items():
        function_map[name] = AggregationQuery(ALL_STATES, funcs)


def run_task(agg_record, query_name):
    agg_date = agg_record.agg_date
    state_ids = agg_record.state_ids
    query = function_map[query_name]
    pre_query, agg_query, post_query = query.funcs
    if pre_query:
        logger.info('Running pre aggregration queries')
        pre_query(agg_date)
        logger.info('Finished pre aggregration queries')
    if query.by_state == SINGLE_STATE:
        greenlets = []
        pool = Pool(15)
        logger.info('Spawning greenlets')
        for state in state_ids:
            greenlets.append(pool.spawn(agg_query, state, agg_date))
        logger.info('Joining greenlets')
        while not pool.join(timeout=120, raise_error=True):
            logger.info('failed to join pool - greenlets remaining: {}'.format(len(pool)))
        logger.info('Getting greenlets')
        for g in greenlets:
            logger.info('getting {}'.format(g))
            g.get()
            logger.info('got {}'.format(g))
        logger.info('Done getting greenlets')
    elif query.by_state == NO_STATES:
        agg_query(agg_date)
    else:
        agg_query(agg_date, state_ids)
    if post_query:
        logger.info('Running post aggregration queries')
        post_query(agg_date)
        logger.info('Finished post aggregration queries')


class Command(BaseCommand):
    help = "Run portion of dashboard aggregation. Used by airflow"

    def add_arguments(self, parser):
        parser.add_argument('query_name')
        parser.add_argument('agg_uuid')

    def handle(self, query_name, agg_uuid, **options):
        setup_tasks()
        agg_record = AggregationRecord.objects.get(agg_uuid=agg_uuid)
        if not agg_record.run_aggregation_queries:
            return

        run_task(agg_record, query_name)
        logger.info('Done with task')
        sys.stdout.flush()
