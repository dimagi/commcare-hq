import csv
import sys

from django.core.management.base import BaseCommand

from corehq.apps.data_analytics.feature_calcs import FEATURE_METRICS
from corehq.apps.data_analytics.models import DomainMetrics


class Command(BaseCommand):
    help = 'Download feature usage metrics for specified domains as CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            'domains',
            nargs='+',
            help='Domain names to download feature metrics for',
        )
        parser.add_argument(
            '--output',
            help='File path to write CSV to (defaults to stdout)',
        )

    def handle(self, *args, **options):
        domains = options['domains']
        output_path = options.get('output')

        fieldnames = ['domain'] + [m.cp_name for m in FEATURE_METRICS]
        metrics_by_domain = {
            m.domain: m
            for m in DomainMetrics.objects.filter(domain__in=domains)
        }
        if output_path:
            with open(output_path, 'w', newline='') as output_file:
                _write_csv(output_file, fieldnames, metrics_by_domain)
        else:
            _write_csv(sys.stdout, fieldnames, metrics_by_domain)


def _write_csv(stream, fieldnames, metrics_by_domain):
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    for domain, metrics in metrics_by_domain.items():
        row = {'domain': domain}
        for metric in FEATURE_METRICS:
            row[metric.cp_name] = getattr(metrics, metric.field_name, None)
        writer.writerow(row)
