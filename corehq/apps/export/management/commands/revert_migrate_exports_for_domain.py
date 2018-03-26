from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from corehq.apps.export.utils import revert_migrate_domain


class Command(BaseCommand):
    help = "Reverts a migrated export domain from new exports to old ones for a given domain"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dryrun',
            default=False,
            help='Runs a dry run on the export reversion',
        )

    def handle(self, domain, **options):
        dryrun = options.pop('dryrun')
        if dryrun:
            print('*** Running in dryrun mode. Will not save any reversions ***')
        revert_migrate_domain(domain, dryrun)
