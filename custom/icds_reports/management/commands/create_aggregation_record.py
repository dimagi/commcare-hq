import logging
from datetime import datetime

from django.core.management.base import BaseCommand

from dateutil.relativedelta import relativedelta

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.models.util import AggregationRecord
from custom.icds_reports.tasks import setup_aggregation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates aggregation record. Used by airflow"

    def add_arguments(self, parser):
        parser.add_argument('agg_uuid')
        parser.add_argument('run_date')
        parser.add_argument('interval')

    def handle(self, agg_uuid, run_date, interval, **options):
        self.run_date = run_date
        self.interval = int(interval)
        state_ids = list(
            SQLLocation.objects
            .filter(domain=DASHBOARD_DOMAIN, location_type__name='state')
            .values_list('location_id', flat=True))

        agg_date = self.get_agg_date()
        agg_record, created = AggregationRecord.objects.get_or_create(
            agg_uuid=agg_uuid,
            defaults={
                'agg_date': agg_date,
                'run_date': run_date,
                'state_ids': state_ids,
                'interval': interval,
            }
        )
        if created:
            logger.info(f'AggregationRecord {agg_uuid} already created')

        # refresh from the db to force date parsing from string to date object
        agg_record.refresh_from_db()

        # if this is a previous month and the previous month should not run
        if agg_record.run_aggregation_queries:
            setup_aggregation(agg_date)

    def get_agg_date(self):
        if self.interval == 0:
            return self.run_date
        else:
            date_object = datetime.strptime(self.run_date, '%Y-%m-%d')
            first_day_of_month = date_object.replace(day=1)
            first_day_next_month = first_day_of_month + relativedelta(months=self.interval + 1)
            agg_date = first_day_next_month - relativedelta(days=1)
            return agg_date.strftime('%Y-%m-%d')
