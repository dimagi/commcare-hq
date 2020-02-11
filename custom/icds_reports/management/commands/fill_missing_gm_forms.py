from django.core.management import BaseCommand
from datetime import datetime

import attr
import logging
import sys
import pytz


from gvent.pool import Pool

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from custom.icds_reports.const import (
    DASHBOARD_DOMAIN
)
from custom.icds_reports.tasks import (
    _get_monthly_dates,
    _update_ucr_table_mapping,
    _update_aggregate_locations_tables,
    icds_aggregation_task

)


class Command(BaseCommand):
    help = "Fills the Missing GM Forms"

    def add_arguments(self, parser):
        parser.add_argument(
            'date', type=int, help='Date of the month whose stunting and wasting data is missing yyyy-mm-dd')

    def handle(self, *args, **kwargs):
        date = kwargs['date']
        date = datetime.strptime(date, '%Y-%m-%d')
        run_task(date)


def run_task(date=None):
    state_time = datetime.now(pytz.utc)
    date = date or state_time.date()
    initial_date = datetime(2017, 1, 1, 0, 0)
    intervals = date.month - initial_date.month + 12 * (date.year - initial_date.year) + 1
    monthly_dates = _get_monthly_dates(date, total_intervals=intervals)
    _update_ucr_table_mapping()

    db_alias = get_icds_ucr_citus_db_alias()
    if db_alias:
        with connections[db_alias].cursor() as cursor:
            _create_aggregate_functions(cursor)
        _update_aggregate_locations_tables()

        state_ids = list(SQLLocation.objects
                         .filter(domain=DASHBOARD_DOMAIN,
                                 location_type__name='state')
                         .values_list('location_id', flat=True))

        for monthly_date in monthly_dates:
            stage_1_tasks = [
                icds_state_aggregation_task.si(state_id=state_id, date=monthly_date,
                                               func_name='_aggregate_gm_forms')
                for state_id in state_ids
            ]
