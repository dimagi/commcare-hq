from optparse import make_option
from django.core.management.base import BaseCommand

from corehq.apps.export.utils import migrate_domain
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Migrates old exports to new ones"

    option_list = (
        make_option(
            '--dry-run',
            action='store_true',
            dest='dryrun',
            default=False,
            help='Runs a dry run on the export conversations'
        ),
    )

    def handle(self, *args, **options):
        dryrun = options.pop('dryrun')
        if dryrun:
            print '*** Running in dryrun mode. Will not save any conversion ***'

        for doc in Domain.get_all(include_docs=False):
            domain = doc['key']
            migrate_domain(domain, dryrun)
