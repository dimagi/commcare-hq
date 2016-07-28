from django.core.management.base import BaseCommand

from corehq.apps.export.utils import migrate_domain
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Migrates old exports to new ones"

    def handle(self, *args, **options):

        for doc in Domain.get_all(include_docs=False):
            domain = doc['key']
            migrate_domain(domain)
