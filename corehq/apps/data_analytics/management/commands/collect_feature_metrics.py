from django.core.management.base import BaseCommand

from corehq.apps.data_analytics.tasks import (
    _collect_feature_metrics_for_domain,
)


class Command(BaseCommand):
    help = 'Collect feature usage metrics for specified domains'

    def add_arguments(self, parser):
        parser.add_argument(
            'domains',
            nargs='+',
            help='Domain names to collect feature metrics for',
        )

    def handle(self, *args, **options):
        domains = options['domains']
        self.stdout.write(
            f'Collecting feature metrics for {len(domains)} '
            f'domain(s)...'
        )
        for domain_name in domains:
            _collect_feature_metrics_for_domain(domain_name)
            self.stdout.write(f'  Processed: {domain_name}')
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Updated {len(domains)} domain(s).'
            )
        )
