from django.conf import settings
from django.core.management.base import BaseCommand

from corehq import toggles
from corehq.toggles import NAMESPACE_DOMAIN

import csv
from pathlib import Path


DOMAINS_CSV = Path(__file__).parent / 'data' / 'domains_using_case_search_FFs.csv'

def get_domains_from_csv():
    with open(DOMAINS_CSV, newline='') as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "Remove case search FFs from internal domains that do not need them (not QA etc.)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            help="Show what would be done without actually removing the FFs",
            action='store_true',
        )

    def handle(self, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write("DRY RUN - No feature flags will be disabled\n")

        domains = toggles.SYNC_SEARCH_CASE_CLAIM.get_enabled_domains()

        env = settings.SERVER_ENVIRONMENT
        domain_2_keep = {
            (d['Environment'], d['Domain Name']): d['Keep']
            for d in get_domains_from_csv() if d['Environment'] == env
        }
        self.stdout.write(f"Checking domains on: '{env}'. Found { len(domain_2_keep) } domains in config\n")

        for domain_name in domains:
            keep = domain_2_keep.get((env, domain_name), None)
            # self.stdout.write(F"env: '{env}', domain: '{domain_name}', keep: {keep}\n")
            if keep is None:
                self.stdout.write(F"Could not find '{domain_name}' for env '{env}' in config file\n")
            elif keep == 'FALSE':
                self.stdout.write(f"Disabled case search FFs for '{domain_name}'\n")
                if not dry_run:
                    toggles.SYNC_SEARCH_CASE_CLAIM.set(domain_name, False, NAMESPACE_DOMAIN)
                    toggles.CASE_SEARCH_ADVANCED.set(domain_name, False, NAMESPACE_DOMAIN)
                    toggles.CASE_SEARCH_RELATED_LOOKUPS.set(domain_name, False, NAMESPACE_DOMAIN)
                    toggles.CASE_SEARCH_DEPRECATED.set(domain_name, False, NAMESPACE_DOMAIN)
                    toggles.CASE_SEARCH_DEPRECATED_NORMAL_CASE_LIST.set(domain_name, False, NAMESPACE_DOMAIN)
