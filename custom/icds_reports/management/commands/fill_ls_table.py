from datetime import date

from celery import chain
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.const import (
    DASHBOARD_DOMAIN
)
from custom.icds_reports.tasks import icds_aggregation_task, icds_state_aggregation_task


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        start_date = date(2017, 3, 1)
        end_date = date(2018, 11, 1)
        state_ids = list(SQLLocation.objects
                         .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
                         .values_list('location_id', flat=True))

        while start_date < end_date:
            print(f"====Running {start_date}====\n")
            calculation_date = start_date.strftime('%Y-%m-%d')
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
            c = chain(*res_ls_tasks).apply_async()
            c.get(disable_sync_subtasks=False)
            start_date = start_date + relativedelta(months=1)
