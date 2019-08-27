from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Marks most recent snapshot of a domain"

    def handle(self, **options):
        print("Migrating snapshot documents to have a marked head")

        for domain in Domain.get_all(include_docs=False):
            head = Domain.view(
                'domain/snapshots',
                startkey=[domain['id'], {}],
                endkey=[domain['id'], None],
                reduce=False,
                include_docs=True,
                descending=True,
                limit=1
            ).first()
            if head:
                head.snapshot_head = True
                head.save()
