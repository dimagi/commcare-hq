import sys

from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Subscription
from corehq.toggles import StaticToggle, Toggle


class Command(BaseCommand):
    help = """
    Prints the list of domains that have <feature_flag> enabled, and
    their subscriptions.
    """

    def add_arguments(self, parser):
        parser.add_argument('feature_flag')

    def handle(self, feature_flag, *args, **options):
        toggle_slug = feature_flag.lower()
        if not toggle_exists(toggle_slug):
            self.stderr.write(f"Feature flag '{feature_flag}' not found")
            sys.exit(1)

        domains = get_enabled_domains(toggle_slug)
        self.stdout.write(f"{len(domains)} domain(s) enabled:")
        for domain in domains:
            subs = get_domain_subscription(domain)
            self.stdout.write(f'{domain}\t({subs})')


def toggle_exists(toggle_slug):
    try:
        Toggle.get(toggle_slug)
    except ResourceNotFound:
        return False
    return True


def get_enabled_domains(toggle_slug):
    toggle = StaticToggle(toggle_slug.lower(), '', '')
    return toggle.get_enabled_domains()


def get_domain_subscription(domain):
    subs = Subscription.get_active_subscription_by_domain(domain)
    return subs.plan_version.plan.name if subs else None
