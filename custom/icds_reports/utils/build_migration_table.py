from corehq.apps.locations.models import SQLLocation
from datetime import date
from custom.icds_reports.tasks import icds_state_aggregation_task
from dateutil.relativedelta import relativedelta

DASHBOARD_DOMAIN='icds-cas'

state_ids = list(SQLLocation.objects
                     .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
                     .values_list('location_id', flat=True))


initial_date = date(2017, 1, 1)
current_date = date(2017, 1, 1)

while current_date <= date(2020, 2, 1):
    for state_id in state_ids:
        icds_state_aggregation_task(state_id=state_id, date=current_date,
                                    func_name='_agg_migration_table')
    current_date = current_date + relativedelta(months=1)



