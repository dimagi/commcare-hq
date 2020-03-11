from django.core.management import BaseCommand
from datetime import datetime

from custom.icds_reports.const import (
    DASHBOARD_DOMAIN
)

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.tasks import (
    _get_monthly_dates,
    icds_state_aggregation_task
)


class Command(BaseCommand):
    help = "Fills the Missing GM Forms"

    def add_arguments(self, parser):
        parser.add_argument(
            'date', type=str, help='Date of the month whose stunting and wasting data is missing yyyy-mm-dd')

    def handle(self, *args, **kwargs):
        date = kwargs['date']
        date = datetime.strptime(date, '%Y-%m-%d')
        run_task(date)

    def run_task(date):
        initial_date = datetime(2017, 3, 1, 0, 0)
        intervals = data.month - initial_date.month + 12 * (date.year - initial_date.year) + 1
        monthly_dates = _get_monthly_dates(date, total_intervals=intervals)

        state_ids = list(SQLLocation.objects.filter(domain=DASHBOARD_DOMAIN,
                                                    location_type__name='state').values_list('location_id', flat=True))
        for monthly_date in monthly_dates:
            for state_id in state_ids:
                icds_state_aggregation_task(state_id=state_id, date=monthly_date,
                                            func_name='_aggregate_gm_forms')
