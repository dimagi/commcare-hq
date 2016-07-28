from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Marks most recent snapshot of a domain"
    args = ""

    def handle(self, *args, **options):
        print "Migrating snapshot documents to have a marked head"

        for domain in Domain.get_all(include_docs=False):
            head = Domain.get_db().view(
                'domain/snapshots',
                startkey=[domain['id'], {}],
                endkey=[domain['id'], None],
                reduce=False,
                include_docs=True,
                descending=True
            ).first()
            if head:
                domain_object = Domain.wrap(head['doc'])
                domain_object.snapshot_head = True
                domain_object.save()
