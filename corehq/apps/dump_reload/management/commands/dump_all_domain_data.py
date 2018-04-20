from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument(
            '-e', '--exclude', dest='exclude', action='append', default=[],
            help='An app_label or app_label.ModelName to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).'
        )
        parser.add_argument(
            '--console', action='store_true', default=False, dest='console',
            help='Write output to the console instead of to file.'
        )
        parser.add_argument('--dumper', dest='dumpers', action='append', default=[],
                            help='Dumper slug to run (use multiple --dumper to run multiple dumpers).')
        parser.add_argument('-e', '--exporter', dest='exporters', action='append', default=[],
                            help='Exporter slug to run '
                                 '(use multiple --slug to run multiple exporters or --all to run them all).')
        parser.add_argument('--all', action='store_true', default=False,
                            help='Run all exporters')
        parser.add_argument('--chunk-size', type=int, default=100,
                            help='Maximum number of records to read from couch at once.')
        parser.add_argument('--limit-to-db', dest='limit_to_db',
                            help="When specifying a SQL importer use this to restrict "
                                 "the exporter to a single database.")

    def handle(self, domain_name, **options):
        call_command('dump_domain_data', domain_name, options)
        call_command('run_blob_export', domain_name, options)
