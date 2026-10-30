
from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.tasks import icds_state_aggregation_task
import os
import datetime

from django.core.management.base import BaseCommand
from corehq.util.argparse_types import date_type
from django.db import connections, transaction

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


@transaction.atomic
def _run_custom_sql_script(command, day=None):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command, [day])


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'month',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD'
        )

    def build_jan_data(self):
        path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'build_migration_table_jan.sql')
        with open(path, "r", encoding='utf-8') as sql_file:
            sql_to_execute = sql_file.read()
            _run_custom_sql_script(sql_to_execute)

    def build_month_data(self, month):
        DASHBOARD_DOMAIN = 'icds-cas'
        state_ids = list(SQLLocation.objects
                         .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
                         .values_list('location_id', flat=True))
        for state_id in state_ids:
            icds_state_aggregation_task(state_id=state_id, date=month,
                                        func_name='_agg_migration_table')

    def handle(self, month, *args, **options):

        if month == datetime.date(2020, 1, 1):
            self.build_jan_data()
        else:
            self.build_month_data(month)
