from __future__ import print_function
import csv

from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domain.dbaccessors import get_domain_ids_by_names

from corehq.util.couch import iter_update, DocUpdate
from corehq.apps.domain.models import Domain, BUSINESS_UNITS


class Command(BaseCommand):
    help = """
    Migrate domain business_unit. Takes a CSV with the following columns:

    domain, business_unit
    """
    args = "migration_file"
    label = "migration csv file"

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("Usage is ./manage.py migrate_domain_bu [migration_file]!")

        name_by_map = {}
        with open(args[0], 'rb') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            for row in reader:
                name_by_map[row[0]] = row[1]

        domain_ids = get_domain_ids_by_names(name_by_map.keys())

        def update_domain(doc):
            domain = Domain.wrap(doc)
            new_bu = name_by_map[domain.name]
            if new_bu not in BUSINESS_UNITS:
                print('Unknown BU: domain={}, BU={}'.format(domain.name, new_bu))
                return
            domain.internal.business_unit = new_bu
            return DocUpdate(doc)

        iter_update(Domain.get_db(), update_domain, domain_ids, verbose=True)
