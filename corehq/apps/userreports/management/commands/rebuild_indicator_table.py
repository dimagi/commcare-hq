from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.userreports import tasks


class Command(BaseCommand):
    help = "Rebuild a user configurable reporting table"

    def add_arguments(self, parser):
        parser.add_argument('indicator_config_id')

    def handle(self, indicator_config_id, **options):
        tasks.rebuild_indicators(indicator_config_id)
