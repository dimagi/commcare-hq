import csv

from django.core.management.base import LabelCommand, CommandError

from corehq.util.couch import iter_update, DocUpdate
from corehq.apps.domain.models import Domain


class Command(LabelCommand):
    help = """
    Migrate domain business_unit. Takes a CSV with the following columns:

    domain, business_unit
    """
    args = "migration_file"
    label = "migration csv file"

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("Usage is ./manage.py migrate_domain_bu [migration_file]!")

        updates = {}
        with open(args[0], 'rb') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            for row in reader:
                updates[Domain.get_by_name(row[0])['_id']] = row[1]

        def update_domain(doc):
            Domain.wrap(doc).internal.business_unit = updates[doc['_id']]
            return DocUpdate(doc)

        iter_update(Domain.get_db(), update_domain, updates.keys(), verbose=True)
