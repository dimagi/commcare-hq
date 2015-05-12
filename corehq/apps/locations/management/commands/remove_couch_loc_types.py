from django.core.management.base import BaseCommand
from dimagi.utils.couch.database import iter_docs
from corehq.apps.domain.models import Domain
from corehq.util.couch import IterativeSaver


class Command(BaseCommand):
    help = "(2015-04-02) Delete the location_types property on Domain"

    def handle(self, *args, **kwargs):
        domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
        with IterativeSaver(Domain.get_db()) as iter_db:
            for domain_doc in iter_docs(Domain.get_db(), domain_ids):
                if (
                    domain_doc.pop('location_types', None) or
                    domain_doc.pop('obsolete_location_types', None)
                ):
                    print ("Removing location_types from domain {} - {}"
                           .format(domain_doc['name'], domain_doc['_id']))
                    iter_db.save(domain_doc)
