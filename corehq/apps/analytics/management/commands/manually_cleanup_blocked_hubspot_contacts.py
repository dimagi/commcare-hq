from django.core.management import BaseCommand

from corehq.apps.analytics.utils import (
    remove_blocked_domain_contacts_from_hubspot,
)


class Command(BaseCommand):
    help = "Manually cleans up blocked Hubspot contacts"

    def handle(self, **options):
        remove_blocked_domain_contacts_from_hubspot(self.stdout)
