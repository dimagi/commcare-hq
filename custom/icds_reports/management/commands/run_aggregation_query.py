from __future__ import absolute_import, print_function, unicode_literals

import attr
import datetime
from dateutil.relativedelta import relativedelta
from gevent.pool import Pool

from django.core.cache import cache
from django.core.management import CommandError
from django.core.management.base import BaseCommand

from custom.icds_reports.tasks.models.util import AggregationRecord
from custom.icds_reports.tasks import (
    _aggregate_gm_forms, _aggregate_df_forms, _aggregate_cf_forms, _aggregate_ccs_cf_forms,
    _aggregate_child_health_thr_forms, _aggregate_ccs_record_thr_forms, _aggregate_child_health_pnc_forms,
    _aggregate_ccs_record_pnc_forms, _aggregate_delivery_forms, _aggregate_bp_forms,
    _aggregate_awc_infra_forms, _child_health_monthly_table, _agg_ls_awc_mgt_form, _agg_ls_vhnd_form,
    _agg_beneficiary_form, create_mbt_for_month, setup_aggregation, _agg_ls_table,
    _update_months_table, _daily_attendance_table, _agg_child_health_table,
    _ccs_record_monthly_table, _agg_ccs_record_table, _agg_awc_table,
    aggregate_awc_daily, email_dashboad_team, _child_health_monthly_aggregation
)


STATE_TASKS = {
    'aggregate_gm_forms': _aggregate_gm_forms,
    'aggregate_df_forms': _aggregate_df_forms,
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
    'create_mbt_for_month': create_mbt_for_month
}

ALL_STATES_TASKS = {
    'child_health_monthly': _child_health_monthly_aggregation,
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


class Command(BaseCommand):
    help = "Run portion of dashboard aggregation. Used by airflow"

    def add_arguments(self, parser):
        parser.add_argument('query_name')
        parser.add_argument('agg_uuid')

    def handle(self, query_name, agg_uuid, **options):
        self.function_map = {}
        self.setup_tasks()
        agg_record = AggregationRecord.objects.get(agg_uuid=agg_uuid)
        agg_date = agg_record.agg_date
        state_ids = agg_record.state_ids
        query = self.function_map[query_name]
        if query.by_state == SINGLE_STATE:
            pool = Pool(10)
            for state in state_ids:
                pool.spawn(query.func, state, agg_date)
            pool.join()
        elif query.by_state == NO_STATES:
            query.func(agg_date)
        else:
            state_ids
            query.func(agg_date, state_ids)

    def setup_tasks(self):
        for name, func in STATE_TASKS.items():
            self.function_map[name] = AggregationQuery(SINGLE_STATE, func)
        for name, func in NORMAL_TASKS.items():
            self.function_map[name] = AggregationQuery(NO_STATES, func)
        for name, func in ALL_STATES_TASKS.items():
            self.function_map[name] = AggregationQuery(ALL_STATES, func)
