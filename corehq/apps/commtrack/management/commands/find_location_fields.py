from django.core.management.base import BaseCommand
from corehq.apps.locations.models import Location


class Command(BaseCommand):
    # frequency domain/property
    def has_any_hardcoded_properties(self, loc):
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
                    self.stdout.write(
                        "Found location %s (%s) in domain %s with %s set to %s" % (
                            loc._id,
                            loc.location_type,
                            loc.domain,
                            prop,
                            prop_val
                        )
                    )
                    found = True

        return found

    def handle(self, *args, **options):
        self.stdout.write("Populating site codes...\n")

        relevant_ids = set([r['id'] for r in Location.get_db().view(
            'locations/by_type',
            reduce=False,
        ).all()])

        problematic_domains = {}

        for loc_id in relevant_ids:
            loc = Location.get(loc_id)
            if self.has_any_hardcoded_properties(loc):
                if loc.domain in problematic_domains:
                    problematic_domains[loc.domain] += 1
                else:
                    problematic_domains[loc.domain] = 1

        self.stdout.write("\nDomain stats:\n")
        for domain, count in problematic_domains.iteritems():
            self.stdout.write("%s: %d" % (domain, count))
