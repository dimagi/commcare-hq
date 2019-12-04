from django.core.management.base import BaseCommand

import attr
from gevent.pool import Pool

from custom.icds_reports.models.util import AggregationRecord
from custom.icds_reports.tasks import (
    _agg_awc_table,
    _agg_beneficiary_form,
    _agg_ccs_record_table,
    _agg_child_health_table,
    _agg_ls_awc_mgt_form,
    _agg_ls_table,
    _agg_ls_vhnd_form,
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
    _ccs_record_monthly_table,
    _child_health_monthly_aggregation,
    _daily_attendance_table,
    _update_months_table,
    aggregate_awc_daily,
    create_all_mbt,
    setup_aggregation,
    update_child_health_monthly_table,
)

STATE_TASKS = {
    'aggregate_gm_forms': _aggregate_gm_forms,
    'aggregate_cf_forms': _aggregate_cf_forms,
    'aggregate_ccs_cf_forms': _aggregate_ccs_cf_forms,
    'aggregate_child_health_thr_forms': _aggregate_child_health_thr_forms,
    'aggregate_ccs_record_thr_forms': _aggregate_ccs_record_thr_forms,
    'aggregate_child_health_pnc_forms': _aggregate_child_health_pnc_forms,
    'aggregate_ccs_record_pnc_forms': _aggregate_ccs_record_pnc_forms,
    'aggregate_delivery_forms': _aggregate_delivery_forms,
    'aggregate_bp_forms': _aggregate_bp_forms,
    'aggregate_awc_infra_forms': _aggregate_awc_infra_forms,
    'agg_ls_awc_mgt_form': _agg_ls_awc_mgt_form,
    'agg_ls_vhnd_form': _agg_ls_vhnd_form,
    'agg_beneficiary_form': _agg_beneficiary_form,
    'aggregate_df_forms': _aggregate_df_forms,
}

ALL_STATES_TASKS = {
    'child_health_monthly': _child_health_monthly_aggregation,
    'update_child_health_monthly_table': update_child_health_monthly_table,
    'create_mbt_for_month': create_all_mbt,
}

NORMAL_TASKS = {
    'setup_aggregation': setup_aggregation,
    'agg_ls_table': _agg_ls_table,
    'update_months_table': _update_months_table,
    'daily_attendance': _daily_attendance_table,
    'agg_child_health': _agg_child_health_table,
    'ccs_record_monthly': _ccs_record_monthly_table,
    'agg_ccs_record': _agg_ccs_record_table,
    'agg_awc_table': _agg_awc_table,
    'aggregate_awc_daily': aggregate_awc_daily,
}


SINGLE_STATE = 'single'
ALL_STATES = 'all'
NO_STATES = 'none'


@attr.s
class AggregationQuery(object):
    by_state = attr.ib()
    func = attr.ib()


function_map = {}


def setup_tasks():
    for name, func in STATE_TASKS.items():
        function_map[name] = AggregationQuery(SINGLE_STATE, func)
    for name, func in NORMAL_TASKS.items():
        function_map[name] = AggregationQuery(NO_STATES, func)
    for name, func in ALL_STATES_TASKS.items():
        function_map[name] = AggregationQuery(ALL_STATES, func)


def run_task(agg_record, query_name):
    agg_date = agg_record.agg_date
    state_ids = agg_record.state_ids
    query = function_map[query_name]
    if query.by_state == SINGLE_STATE:
        greenlets = []
        pool = Pool(15)
        for state in state_ids:
            greenlets.append(pool.spawn(query.func, state, agg_date))
        pool.join(raise_error=True)
        for g in greenlets:
            g.get()
    elif query.by_state == NO_STATES:
        query.func(agg_date)
    else:
        state_ids
        query.func(agg_date, state_ids)


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
