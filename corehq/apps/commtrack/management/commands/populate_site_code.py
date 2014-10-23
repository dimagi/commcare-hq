from django.core.management.base import BaseCommand
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.util import generate_code
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    help = 'Generate missing site codes for locations'

    def handle(self, *args, **options):
        self.stdout.write("Populating site codes...\n")

        site_codes_by_domain = {}

        relevant_ids = set([r['id'] for r in Location.get_db().view(
            'locations/by_type',
            reduce=False,
        ).all()])

        to_save = []

        for loc in iter_docs(Location.get_db(), relevant_ids):
            if not loc['site_code']:
                # triggering the safe will cause this to get populated
                self.stdout.write("Updating location %s\n" % loc['name'])

                if loc['domain'] not in site_codes_by_domain:
                    site_codes_by_domain[loc['domain']] = list(
                        Location.site_codes_for_domain(loc['domain'])
                    )

                loc['site_code'] = generate_code(
                    loc['name'],
                    site_codes_by_domain[loc['domain']]
                )
                site_codes_by_domain[loc['domain']].append(loc['site_code'])

                to_save.append(loc)

                if len(to_save) > 500:
                    Location.get_db().bulk_save(to_save)
                    to_save = []

        if to_save:
            Location.get_db().bulk_save(to_save)
