from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.toggles import NAMESPACE_DOMAIN, all_toggles_by_name, set_toggle


class Command(BaseCommand):
    help = "Disable toggles for domains that no longer exist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            help="Actually disable toggles",
            action='store_true',
        )

    def handle(self, **options):
        all_toggles = all_toggles_by_name()
        domain_existence = {}
        for toggle in all_toggles.values():
            for domain in toggle.get_enabled_domains():
                if domain not in domain_existence:
                    domain_existence[domain] = bool(Domain.get_by_name(domain))
                if not domain_existence[domain]:
                    prefix = '[DRY RUN] ' if not options['save'] else ''
                    print(f"{prefix}Disabling {toggle.slug} for {domain}")
                    if options['save']:
                        set_toggle(toggle.slug, domain, False, NAMESPACE_DOMAIN)
