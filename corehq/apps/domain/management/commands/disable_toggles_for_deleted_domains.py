from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.models import Domain
from corehq.toggles import NAMESPACE_DOMAIN, all_toggles_by_name, set_toggle, Toggle
from corehq.toggles.shortcuts import find_domains_with_toggle_enabled


class Command(BaseCommand):
    help = "Disable toggles for domains that no longer exist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            help="Actually disable toggles",
            action='store_true',
        )
        parser.add_argument('--domain', help="Only update this domain")
        parser.add_argument('--slug', help="Only update this toggle")

    def handle(self, **options):
        if options['slug']:
            try:
                toggles = [Toggle.get(options['slug'])]
            except ResourceNotFound:
                raise CommandError(f"Slug {options['slug']} not found - are you using the lowercase slug?")
        else:
            toggles = all_toggles_by_name().values()

        domain = options['domain']
        domain_existence = {}
        for toggle in toggles:
            domains = []
            if domain:
                if domain in find_domains_with_toggle_enabled(toggle):
                    domains = [domain]
            else:
                domains = find_domains_with_toggle_enabled(toggle)

            for domain in domains:
                if domain not in domain_existence:
                    domain_existence[domain] = bool(Domain.get_by_name(domain))
                if not domain_existence[domain]:
                    prefix = '[DRY RUN] ' if not options['save'] else ''
                    print(f"{prefix}Disabling {toggle.slug} for {domain}")
                    if options['save']:
                        set_toggle(toggle.slug, domain, False, NAMESPACE_DOMAIN)
