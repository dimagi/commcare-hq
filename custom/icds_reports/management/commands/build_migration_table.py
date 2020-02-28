
import datetime
from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.tasks import icds_state_aggregation_task
from dateutil.relativedelta import relativedelta


class Command(BaseCommand):
    def handle(self, *args, **options):
        DASHBOARD_DOMAIN = 'icds-cas'

        state_ids = list(SQLLocation.objects
                         .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
                         .values_list('location_id', flat=True))

        current_date = datetime.date(2020, 1, 1)

        while current_date <= datetime.date(2020, 2, 1):
            for state_id in state_ids:
                icds_state_aggregation_task(state_id=state_id, date=current_date,
                                            func_name='_agg_migration_table')
            current_date = current_date + relativedelta(months=1)
