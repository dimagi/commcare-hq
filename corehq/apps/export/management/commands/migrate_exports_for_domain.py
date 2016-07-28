from django.core.management.base import LabelCommand

from corehq.apps.export.utils import migrate_domain


class Command(LabelCommand):
    help = "Migrates old exports to new ones for a given domain"

    def handle(self, domain, *args, **options):
        migrate_domain(domain)
