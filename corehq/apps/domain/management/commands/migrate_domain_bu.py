from __future__ import print_function
from __future__ import absolute_import
import csv

from django.core.management.base import BaseCommand
from corehq.apps.domain.dbaccessors import get_domain_ids_by_names

from corehq.util.couch import iter_update, DocUpdate
from corehq.apps.domain.models import Domain, BUSINESS_UNITS


class Command(BaseCommand):
    help = """
    Migrate domain business_unit. Takes a CSV with the following columns:

    domain, business_unit
    """

    def add_arguments(self, parser):
        parser.add_argument('migration_file')

    def handle(self, migration_file, **options):
        name_by_map = {}
        with open(migration_file, 'rb') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            for row in reader:
                name_by_map[row[0]] = row[1]

        domain_ids = get_domain_ids_by_names(list(name_by_map))

        def update_domain(doc):
            domain = Domain.wrap(doc)
            new_bu = name_by_map[domain.name]
            if new_bu not in BUSINESS_UNITS:
                print('Unknown BU: domain={}, BU={}'.format(domain.name, new_bu))
                return
            domain.internal.business_unit = new_bu
            return DocUpdate(doc)

        iter_update(Domain.get_db(), update_domain, domain_ids, verbose=True)
