from collections import defaultdict

from django.core.management import BaseCommand

from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.tasks import _queue_indicators


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('data_source_ids')
        parser.add_argument('--agg-queue', dest='use_agg_queue', action='store_true')

    def handle(self, data_source_ids, use_agg_queue, **options):
        indicators = AsyncIndicator.objects.filter(indicator_config_ids__contains=[data_source_ids])
        _queue_indicators(indicators, use_agg_queue=use_agg_queue)
