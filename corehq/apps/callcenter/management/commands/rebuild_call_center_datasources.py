from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
import math

import sys
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.callcenter.checks import get_call_center_data_source_stats
from corehq.apps.callcenter.data_source import TABLE_IDS
from corehq.apps.callcenter.utils import get_call_center_domains
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators


class Command(BaseCommand):
    help = "Rebuild call center data sources which are out of sync"

    def add_arguments(self, parser):
        parser.add_argument(
            'domains',
            nargs='+',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            default=False,
            help='Check ALL domains',
        )
        parser.add_argument(
            '--threshold',
            type=int,
            default=20,
            help='Threshold above which data source will be rebuilt (percentage difference between ES and UCR)',
        )
        parser.add_argument(
            '--initiated-by', required=True, action='store',
            dest='initiated', help='Who initiated the rebuild'
        )

    def handle(self, domains, **options):
        if not domains and not options['all']:
            raise CommandError('Specify specific domains or --all')

        all_domains = [domain.name for domain in get_call_center_domains() if domain.use_fixtures]
        if domains:
            for domain in domains:
                assert domain in all_domains, "Domain '{}' is not a Call Center domain".format(domain)
        else:
            domains = all_domains

        threshold = options['threshold']
        domain_stats = get_call_center_data_source_stats(domains)
        for domain in domains:
            stats = domain_stats[domain]
            print('Checking domain:', domain)
            if stats.error:
                print('Error getting stats:\n', stats.error)
                continue

            for stat in stats.iter_data_source_stats():
                diff = math.fabs(stat.ucr_percent - stat.es_percent)
                if diff > threshold:
                    print("rebuilding data source '{}' in domain '{}': diff = {}".format(
                        stat.name, domain, diff
                    ))
                    try:
                        rebuild_indicators(
                            StaticDataSourceConfiguration.get_doc_id(domain, TABLE_IDS[stat.name]),
                            initiated_by=options['initiated'],
                            source='rebuild_call_center_datasources'
                        )
                    except Exception as e:
                        sys.stderr.write("Error rebuilding data source '{}' in domain '{}':\n{}".format(
                            stat.name, domain, e
                        ))
