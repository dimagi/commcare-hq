from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.userreports import tasks


class Command(BaseCommand):
    help = "Rebuild a user configurable reporting table"

    def add_arguments(self, parser):
        parser.add_argument('indicator_config_id')
        parser.add_argument('--in-place', action='store_true', dest='in_place', default=False,
                            help='Rebuild table in place (preserve existing data)')
        parser.add_argument('--initiated-by', action='store', required=True, dest='initiated',
                            help='Who initiated the rebuild (for sending email notifications)')

    def handle(self, indicator_config_id, **options):
        if options['in_place']:
            tasks.rebuild_indicators_in_place(
                indicator_config_id, options['initiated'], source='rebuild_indicator_table'
            )
        else:
            tasks.rebuild_indicators(
                indicator_config_id,
                initiated_by=options['initiated'],
                source='rebuild_indicator_table'
            )
