from django.core.management import BaseCommand

from corehq.apps.analytics.utils import (
    get_blocked_hubspot_domains,
    get_blocked_hubspot_accounts,
)


class Command(BaseCommand):
    help = "List all domains and email domains blocked from Hubspot"

    def handle(self, **options):
        blocked_domains = get_blocked_hubspot_domains()
        blocked_hubspot_accounts = get_blocked_hubspot_accounts()

        self.stdout.write('\n\nDomains Blocked From Hubspot\n')
        self.stdout.write('\n'.join(blocked_domains))

        self.stdout.write('\n\nAccounts Blocked From Hubspot\n')
        self.stdout.write('\n'.join(blocked_hubspot_accounts))

        self.stdout.write('\n\n')
