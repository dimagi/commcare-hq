from __future__ import print_function
from optparse import make_option
from django.core.management.base import BaseCommand

from corehq.apps.export.utils import migrate_domain


class Command(BaseCommand):
    help = "Migrates old exports to new ones for a given domain"

    option_list = (
        make_option(
            '--dry-run',
            action='store_true',
            dest='dryrun',
            default=False,
            help='Runs a dry run on the export conversations'
        ),
        make_option(
            '--force-convert-columns',
            action='store_true',
            dest='force_convert_columns',
            default=False,
            help='Force convert columns that were not found in the new schema'
        ),
    )

    def handle(self, domain, *args, **options):
        dryrun = options.pop('dryrun')
        force_convert_columns = options.pop('force_convert_columns')
        if dryrun:
            print('*** Running in dryrun mode. Will not save any conversion ***')
        migrate_domain(domain, dryrun, force_convert_columns=force_convert_columns)
