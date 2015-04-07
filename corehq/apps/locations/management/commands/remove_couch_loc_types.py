from django.core.management.base import BaseCommand
from dimagi.utils.couch.database import iter_docs
from corehq.apps.domain.models import Domain


class IterativeSaver(object):
    """
    Bulk save docs in chunks.

        with IterativeSaver(db) as iter_db:
            for doc in iter_docs(db)
                iter_db.save(doc)
    """
    def __init__(self, database, chunksize=100):
        self.db = database
        self.chunksize = chunksize

    def __enter__(self):
        self.to_save = []
        return self

    def commit(self):
        self.db.bulk_save(self.to_save)
        self.to_save = []

    def save(self, doc):
        self.to_save.append(doc)
        if len(self.to_save) >= self.chunksize:
            self.commit()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.to_save:
            self.commit()


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
