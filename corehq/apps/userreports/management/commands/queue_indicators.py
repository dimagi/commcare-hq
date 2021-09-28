from collections import defaultdict

from django.core.management import BaseCommand

from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.tasks import _queue_indicators


class Command(BaseCommand):
    help = "Queue all of the docs in the async indicators table for a given datasource"

    def add_arguments(self, parser):
        parser.add_argument('data_source_id', help='id of data source to queue')
        parser.add_argument('--agg-queue', dest='use_agg_queue', action='store_true',
                            help='Use the aggregation queue instead of the async UCR queue to avoid competing with normal async UCR processing')

    def handle(self, data_source_id, use_agg_queue, **options):
        indicators = AsyncIndicator.objects.filter(indicator_config_ids__contains=[data_source_id])
        _queue_indicators(indicators, use_agg_queue=use_agg_queue)
