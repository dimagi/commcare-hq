from __future__ import absolute_import
from __future__ import print_function
import csv
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation
from custom.enikshay.integrations.bets.repeaters import BETSLocationRepeater
from custom.enikshay.integrations.bets.utils import get_bets_location_json
from six.moves import map


class Command(BaseCommand):
    field_names = [
        'domain',
        'parent_site_code',
        'is_archived',
        'last_modified',
        'location_id',
        'location_type',
        'location_type_code',
        'lineage',
        'doc_type',
        'name',
        'site_code',
        'longitude',
        'ancestors_by_type.ctd',
        'ancestors_by_type.sto',
        'ancestors_by_type.dto',
        'ancestors_by_type.cto',
        'latitude',
        '_id',
        'external_id',
        'metadata.is_test',
        'metadata.tests_available',
        'metadata.private_sector_org_id',
        'metadata.nikshay_code',
        'metadata.enikshay_enabled',
    ]

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        self.domain = domain
        filename = 'eNikshay_locations.csv'
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(self.field_names)
            loc_types = BETSLocationRepeater.location_types_to_forward
            for loc in (SQLLocation.active_objects
                        .filter(domain=domain, location_type__code__in=loc_types)
                        .prefetch_related('parent', 'location_type')):
                if loc.metadata.get('is_test') != "yes":
                    self.add_loc(loc, writer)
        print("Wrote to {}".format(filename))

    def add_loc(self, location, writer):
        loc_data = get_bets_location_json(location)

        def get_field(field):
            if field == 'lineage':
                return ''
            elif '.' in field:
                obj, key = field.split('.')
                return loc_data[obj].get(key, '')
            return loc_data[field]

        writer.writerow(list(map(get_field, self.field_names)))
