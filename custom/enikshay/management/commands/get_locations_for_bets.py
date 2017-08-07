import csv
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation
from custom.enikshay.integrations.bets.repeaters import BETSLocationRepeater


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        self.domain = domain
        filename = 'eNikshay_locations.csv'
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'name',
                'site_code',
                'location_id',
                'doc_type',
                'domain',
                'external_id',
                'is_archived',
                'last_modified',
                'latitude',
                'longitude',
                # TODO exactly which metadata fields do they want? How do we
                # serialize the headers, metadata.is_test?
                # 'metadata',
                'location_type',
                'location_type_code',
                'parent_location_id',
                'parent_site_code',
                # They may also want ancestors_by_type, TBD
            ])
            loc_types = BETSLocationRepeater.location_types_to_forward
            for loc in (SQLLocation.active_objects
                        .filter(domain=domain, location_type__name__in=loc_types)
                        .prefetch_related('parent', 'location_type')):
                self.add_loc(loc, writer)
        print "Wrote to {}".format(filename)

    def add_loc(self, location, writer):
        if location.metadata.get('is_test') != "yes":
            return

        writer.writerow([
            location.name,
            location.site_code,
            location.location_id,
            'Location',
            location.domain,
            location.external_id,
            location.is_archived,
            location.last_modified.isoformat(),
            float(location.latitude) if location.latitude else None,
            float(location.longitude) if location.longitude else None,
            # location.metadata,
            location.location_type.name,
            location.location_type.code,
            location.parent_location_id,
            location.parent.site_code,
            # They may also want ancestors_by_type, if so, use
            # custom.enikshay.integrations.bets.utils.get_bets_location_json
        ])
