from django.core.management.base import BaseCommand
from corehq.apps.locations.models import Location


class Command(BaseCommand):
    help = 'Generate missing site codes for locations'

    def handle(self, *args, **options):
        self.stdout.write("Populating site codes...\n")

        relevant_ids = set([r['id'] for r in Location.get_db().view(
            'locations/by_type',
            reduce=False,
        ).all()])

        for loc_id in relevant_ids:
            loc = Location.get(loc_id)
            if not loc.site_code:
                # triggering the safe will cause this to get populated
                self.stdout.write("Updating location %s\n" % loc.name)
                loc.save()
