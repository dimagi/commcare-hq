import dateutil
from django.core.management import BaseCommand

from corehq.apps.hqadmin.couch_domain_utils import (
    cleanup_stale_es_on_couch_domains,
)

ALL_COUCH_DOMAINS = object()


class Command(BaseCommand):
    help = """Force a sync of data on all high priority couch db domains
    (determined by the feature flag ACTIVE_COUCH_DOMAINS)"""

    def add_arguments(self, parser):
        parser.add_argument('--domains', default=ALL_COUCH_DOMAINS)
        parser.add_argument(
            '--start',
            action='store',
            help='Only include data modified after this date',
        )
        parser.add_argument(
            '--end',
            action='store',
            help='Only include data modified before this date',
        )

    def handle(self, **options):
        start = dateutil.parser.parse(options['start']) if options[
            'start'] else None
        end = dateutil.parser.parse(options['end']) if options[
            'end'] else None
        domains = options['domains'].split(',') if options['domains'] else None
        num_domains = len(domains) if domains else "ALL"
        self.stdout.write(f"\nSyncing {num_domains} couch domains:\n")
        cleanup_stale_es_on_couch_domains(
            start_date=start, end_date=end, domains=domains, stdout=self.stdout
        )
