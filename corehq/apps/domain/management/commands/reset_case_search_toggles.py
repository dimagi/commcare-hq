
from django.core.management.base import BaseCommand

from corehq import toggles
from corehq.toggles import NAMESPACE_DOMAIN

class Command(BaseCommand):
    help = "Reset migrated to new Case Search toggles"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            help="Show what would be done without actually setting toggles",
            action='store_true',
        )
        parser.add_argument(
            '--domains',
            help="Comma-separated list of domains to process instead of all SYNC_SEARCH_CASE_CLAIM domains",
            type=lambda s: [d.strip() for d in s.split(',')],
        )


    def reset_toggle(self, domain_name, toggle, dry_run):
        if toggle.enabled(domain_name, namespace=NAMESPACE_DOMAIN):
            self.stdout.write(f"  {toggle.slug}")
            if not dry_run:
                toggle.set(domain_name, False, NAMESPACE_DOMAIN)

    def handle(self, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write("DRY RUN - No toggles will be reset\n")

        domains = options['domains'] or toggles.SYNC_SEARCH_CASE_CLAIM.get_enabled_domains()
        for domain_name in domains:
            self.stdout.write(f"for domain '{domain_name}' reset:")
            self.reset_toggle(domain_name, toggles.CASE_SEARCH_ADVANCED, dry_run)
            self.reset_toggle(domain_name, toggles.CASE_SEARCH_DEPRECATED, dry_run)
            self.reset_toggle(domain_name, toggles.CASE_SEARCH_RELATED_LOOKUPS, dry_run)
            self.stdout.write("\n")
