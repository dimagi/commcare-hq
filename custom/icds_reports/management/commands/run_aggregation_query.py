from __future__ import absolute_import, print_function, unicode_literals

import attr
import datetime
from dateutil.relativedelta import relativedelta
from gevent.pool import Pool

from django.core.cache import cache
from django.core.management import CommandError
from django.core.management.base import BaseCommand

from custom.icds_reports.tasks import (
    _aggregate_gm_forms, _aggregate_df_forms, _aggregate_cf_forms, _aggregate_ccs_cf_forms,
    _aggregate_child_health_thr_forms, _aggregate_ccs_record_thr_forms, _aggregate_child_health_pnc_forms,
    _aggregate_ccs_record_pnc_forms, _aggregate_delivery_forms, _aggregate_bp_forms,
    _aggregate_awc_infra_forms, _child_health_monthly_table, _agg_ls_awc_mgt_form, _agg_ls_vhnd_form,
    _agg_beneficiary_form, create_mbt_for_month, setup_aggregation, _agg_ls_table,
    _update_months_table, _daily_attendance_table, _agg_child_health_table,
    _ccs_record_monthly_table, _agg_ccs_record_table, _agg_awc_table, _agg_awc_table_weekly,
    aggregate_awc_daily, email_dashboad_team
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

ALL_STATES = {

}

NORMAL_TASKS = {
    'setup_aggregation': setup_aggregation,
    'agg_ls_table': _agg_ls_table,
    'update_months_table': _update_months_table,
    'daily_attendance': _daily_attendance_table,
    'child_health_monthly': _child_health_monthly_aggregation,
    'agg_child_health': _agg_child_health_table,
    'ccs_record_monthly': _ccs_record_monthly_table,
    'agg_ccs_record': _agg_ccs_record_table,
    'agg_awc_table': _agg_awc_table,
    'aggregate_awc_daily': aggregate_awc_daily,
}


@attr.s
class AggregationQuery(object):
    by_state = attr.ib()
    func = attr.ib()


class Command(BaseCommand):
    help = "Run portion of dashboard aggregation. Used by airflow"

    def add_arguments(self, parser):
        parser.add_argument('query_name')
        parser.add_argument('date')
        parser.add_argument('interval', type=int)

    def handle(self, query_name, date, interval, **options):
        self.function_map = {}
        self.setup_tasks()
        agg_date = self.get_agg_date(date, interval)
        query = self.function_map[query_name]
        if query.by_state:
            pool = Pool(10)
            state_ids = cache.get('agg_state_ids_{}'.format(date))
            if not state_ids:
                raise CommandError('Aggregation improperly set up. State ids missing')
            for state in state_ids:
                pool.spawn(query.func, state, agg_date)
            pool.join()
        else:
            query.func(agg_date)

    def setup_tasks(self):
        for name, func in STATE_TASKS.items():
            self.function_map[name] = AggregationQuery(True, func)
        for name, func in NORMAL_TASKS.items():
            self.function_map[name] = AggregationQuery(False, func)

    def get_agg_date(self, date, interval):
        if interval > 0:
            raise CommandError('Requesting future aggregation. Interval must be less than 0')
        if not interval:
            return date
        else:
            date_object = datetime.datetime.strptime(date, '%Y-%m-%d')
            first_day_of_month = date_object.replace(day=1)
            first_day_next_month = first_day_of_month + relativedelta(months=interval + 1)
            agg_date = first_day_next_month - relativedelta(days=1)
            return agg_date.strftime('%Y-%m-%d')
