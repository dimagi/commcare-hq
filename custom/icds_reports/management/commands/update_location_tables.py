from django.core.management.base import BaseCommand

from custom.icds_reports.models.util import AggregationRecord
from custom.icds_reports.tasks import update_aggregate_locations_tables


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('agg_uuid')

    def handle(self, agg_uuid, **options):
        agg_record = AggregationRecord.objects.get(agg_uuid=agg_uuid)
        if not agg_record.run_aggregation_queries:
            return
        update_aggregate_locations_tables()
