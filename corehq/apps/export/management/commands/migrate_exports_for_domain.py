from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from corehq.apps.export.utils import migrate_domain


class Command(BaseCommand):
    help = "Migrates old exports to new ones for a given domain"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dryrun',
            default=False,
            help='Runs a dry run on the export conversations',
        ),
        parser.add_argument(
            '--force-convert-columns',
            action='store_true',
            dest='force_convert_columns',
            default=False,
            help='Force convert columns that were not found in the new schema'
        )

    def handle(self, domain, **options):
        dryrun = options.pop('dryrun')
        force_convert_columns = options.pop('force_convert_columns')
        if dryrun:
            print('*** Running in dryrun mode. Will not save any conversion ***')
        migrate_domain(domain, dryrun, force_convert_columns=force_convert_columns)
