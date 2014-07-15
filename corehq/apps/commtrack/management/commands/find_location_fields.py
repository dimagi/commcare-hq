from django.core.management.base import BaseCommand
from corehq.apps.locations.models import Location
from dimagi.utils.couch.database import iter_docs
import csv


class Command(BaseCommand):
    # frequency domain/property
    def has_any_hardcoded_properties(self, loc, csv_writer):
        hardcoded = {
            'outlet': [
                'outlet_type',
                'outlet_type_other',
                'address',
                'landmark',
                'contact_name',
                'contact_phone',
            ],
            'village': [
                'village_size',
                'village_class',
            ],
        }

        found = False

        if loc.location_type in hardcoded.keys():
            for prop in hardcoded[loc.location_type]:
                prop_val = getattr(loc, prop, '')
                if prop_val:
                    csv_writer.writerow([
                        loc._id,
                        loc.location_type,
                        loc.domain,
                        prop,
                        prop_val
                    ])
                    found = True

        return found

    def handle(self, *args, **options):
        with open('location_results.csv', 'wb+') as csvfile:
            csv_writer = csv.writer(
                csvfile,
                delimiter=',',
                quotechar='|',
                quoting=csv.QUOTE_MINIMAL
            )

            csv_writer.writerow(['id', 'type', 'domain', 'property', 'value'])

            locations = list(set(Location.get_db().view(
                'locations/by_type',
                reduce=False,
                wrapper=lambda row: row['id'],
            ).all()))

            problematic_domains = {}

            for loc in iter_docs(Location.get_db(), locations):
                loc = Location.get(loc['_id'])
                if self.has_any_hardcoded_properties(loc, csv_writer):
                    if loc.domain in problematic_domains:
                        problematic_domains[loc.domain] += 1
                    else:
                        problematic_domains[loc.domain] = 1

            self.stdout.write("\nDomain stats:\n")
            for domain, count in problematic_domains.iteritems():
                self.stdout.write("%s: %d" % (domain, count))
